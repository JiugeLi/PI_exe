package main

import (
	"archive/zip"
	"bytes"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// payload.zip is generated from public runtime files and must never contain credentials.
//
//go:embed payload.zip
var payload []byte

func main() {
	code, err := run()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Pi Portable:", err)
		code = 1
	}
	os.Exit(code)
}

func run() (int, error) {
	cwd, err := os.Getwd()
	if err != nil {
		return 1, err
	}
	executable, err := os.Executable()
	if err != nil {
		return 1, err
	}
	configFile := os.Getenv("PI_PORTABLE_CONFIG")
	if configFile == "" {
		configFile = filepath.Join(filepath.Dir(executable), "config.json")
	}
	configFile, err = filepath.Abs(configFile)
	if err != nil {
		return 1, err
	}
	state := filepath.Join(cwd, ".pi-portable")
	if err := os.MkdirAll(state, 0700); err != nil {
		return 1, err
	}
	sum := sha256.Sum256(payload)
	id := hex.EncodeToString(sum[:])[:20]
	runtimeDir := filepath.Join(state, "runtime", runtime.GOOS+"-"+id)
	if _, err := os.Stat(filepath.Join(runtimeDir, ".complete")); err != nil {
		fmt.Fprintln(os.Stderr, "Pi Portable: 正在展开内置运行环境（首次启动）...")
		if err := unpack(payload, runtimeDir); err != nil {
			return 1, err
		}
		fmt.Fprintln(os.Stderr, "Pi Portable: 准备完成，正在启动 Pi...")
	}
	node := filepath.Join(runtimeDir, "node", "bin", "node")
	if runtime.GOOS == "windows" {
		node = filepath.Join(runtimeDir, "node", "node.exe")
	}
	if err := ensureDefaultFiles(runtimeDir, filepath.Dir(executable), configFile); err != nil {
		return 1, err
	}
	args := append([]string{filepath.Join(runtimeDir, "bootstrap.mjs")}, os.Args[1:]...)
	cmd := exec.Command(node, args...)
	cmd.Dir = cwd
	cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, os.Stdout, os.Stderr
	// Child inherits the console/terminal and receives Ctrl+C itself. Keep the
	// wrapper alive until the original Pi has restored the terminal and exited.
	interrupts := make(chan os.Signal, 2)
	signal.Notify(interrupts, os.Interrupt)
	defer signal.Stop(interrupts)
	cmd.Env = append(os.Environ(), "PI_PORTABLE_STATE="+state, "PI_PORTABLE_RUNTIME="+runtimeDir, "PI_PORTABLE_CONFIG_FILE="+configFile)
	err = cmd.Run()
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		return exitErr.ExitCode(), nil
	}
	return 0, err
}

func ensureDefaultFiles(runtimeDir, appDir, configFile string) error {
	for _, name := range []string{"config.json", "README.zh-CN.md", "README.en.md"} {
		target := filepath.Join(appDir, name)
		if name == "config.json" {
			target = configFile
			if os.Getenv("PI_PORTABLE_CONFIG") != "" {
				continue
			}
		}
		if _, err := os.Stat(target); err == nil {
			continue
		}
		source := filepath.Join(runtimeDir, "defaults", name)
		if name == "config.json" {
			legacy := filepath.Join(appDir, "pi.config.json")
			if _, err := os.Stat(legacy); err == nil {
				source = legacy
			}
		}
		data, err := os.ReadFile(source)
		if err != nil {
			return err
		}
		file, err := os.OpenFile(target, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
		if os.IsExist(err) {
			continue
		}
		if err != nil {
			return err
		}
		_, writeErr := file.Write(data)
		closeErr := file.Close()
		if writeErr != nil {
			return writeErr
		}
		if closeErr != nil {
			return closeErr
		}
	}
	return nil
}

func unpack(data []byte, destination string) error {
	if err := os.MkdirAll(filepath.Dir(destination), 0700); err != nil {
		return err
	}
	stage, err := os.MkdirTemp(filepath.Dir(destination), ".extract-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(stage)
	z, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return err
	}
	progress := newExtractionProgress(z.File)
	defer progress.closeLine()
	for _, entry := range z.File {
		name := filepath.FromSlash(entry.Name)
		if filepath.IsAbs(name) || strings.Contains(entry.Name, "\\") {
			return fmt.Errorf("unsafe archive entry")
		}
		target := filepath.Join(stage, name)
		rel, err := filepath.Rel(stage, target)
		if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
			return fmt.Errorf("unsafe archive entry")
		}
		if entry.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("archive symlinks are unsupported")
		}
		if entry.FileInfo().IsDir() {
			if err := os.MkdirAll(target, 0700); err != nil {
				return err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(target), 0700); err != nil {
			return err
		}
		mode := os.FileMode(0600)
		if entry.Mode()&0111 != 0 {
			mode = 0700
		}
		if err := extractFile(entry, target, mode, progress); err != nil {
			return err
		}
		progress.files++
		progress.render(false)
	}
	if err := os.WriteFile(filepath.Join(stage, ".complete"), []byte("ok\n"), 0600); err != nil {
		return err
	}
	if err := os.Rename(stage, destination); err != nil {
		// A concurrent launcher may have finished the same immutable payload.
		if _, done := os.Stat(filepath.Join(destination, ".complete")); done == nil {
			progress.render(true)
			return nil
		}
		return err
	}
	progress.render(true)
	return nil
}

func extractFile(entry *zip.File, target string, mode os.FileMode, progress *extractionProgress) (err error) {
	src, err := entry.Open()
	if err != nil {
		return err
	}
	defer src.Close()
	dst, err := os.OpenFile(target, os.O_CREATE|os.O_EXCL|os.O_WRONLY, mode)
	if err != nil {
		return err
	}
	_, copyErr := io.Copy(dst, &progressReader{source: src, progress: progress})
	closeErr := dst.Close()
	if copyErr != nil {
		return copyErr
	}
	return closeErr
}

type extractionProgress struct {
	bytes, totalBytes uint64
	files, totalFiles int
	started, updated  time.Time
	inline, openLine  bool
}

func newExtractionProgress(entries []*zip.File) *extractionProgress {
	p := &extractionProgress{started: time.Now()}
	if info, err := os.Stderr.Stat(); err == nil {
		p.inline = info.Mode()&os.ModeCharDevice != 0
	}
	for _, entry := range entries {
		if !entry.FileInfo().IsDir() {
			p.totalFiles++
			p.totalBytes += entry.UncompressedSize64
		}
	}
	p.render(false)
	return p
}

func (p *extractionProgress) render(complete bool) {
	interval := time.Second
	if p.inline {
		interval = 200 * time.Millisecond
	}
	if !complete && !p.updated.IsZero() && time.Since(p.updated) < interval {
		return
	}
	p.updated = time.Now()
	// Small-file creation and decompression both take time. Reserve 100% for
	// successful validation and atomic publication of the completed runtime.
	fraction := 0.0
	if p.totalFiles > 0 {
		fraction += float64(p.files) / float64(p.totalFiles) / 2
	}
	if p.totalBytes > 0 {
		fraction += float64(p.bytes) / float64(p.totalBytes) / 2
	}
	percent := min(99, int(fraction*100))
	if complete {
		percent = 100
	}
	filled := percent * 20 / 100
	bar := strings.Repeat("=", filled) + strings.Repeat("-", 20-filled)
	prefix, suffix := "", "\n"
	if p.inline {
		prefix, suffix = "\r", ""
		p.openLine = true
	}
	fmt.Fprintf(os.Stderr, "%s[%s] %3d%% | %d/%d 文件 | %.1f/%.1f MB | 用时 %ds%s",
		prefix, bar, percent, p.files, p.totalFiles, float64(p.bytes)/1e6,
		float64(p.totalBytes)/1e6, int(time.Since(p.started).Seconds()), suffix)
	if complete {
		p.closeLine()
	}
}

func (p *extractionProgress) closeLine() {
	if p.openLine {
		fmt.Fprintln(os.Stderr)
		p.openLine = false
	}
}

type progressReader struct {
	source   io.Reader
	progress *extractionProgress
}

func (r *progressReader) Read(buffer []byte) (int, error) {
	n, err := r.source.Read(buffer)
	r.progress.bytes += uint64(n)
	r.progress.render(false)
	return n, err
}
