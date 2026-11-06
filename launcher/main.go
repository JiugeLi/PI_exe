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
		configFile = filepath.Join(filepath.Dir(executable), "pi.config.json")
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
		fmt.Fprintln(os.Stderr, "Pi Portable: preparing bundled runtime (first launch only)...")
		if err := unpack(payload, runtimeDir); err != nil {
			return 1, err
		}
	}
	node := filepath.Join(runtimeDir, "node", "bin", "node")
	if runtime.GOOS == "windows" {
		node = filepath.Join(runtimeDir, "node", "node.exe")
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
		if err := extractFile(entry, target, mode); err != nil {
			return err
		}
	}
	if err := os.WriteFile(filepath.Join(stage, ".complete"), []byte("ok\n"), 0600); err != nil {
		return err
	}
	if err := os.Rename(stage, destination); err != nil {
		// A concurrent launcher may have finished the same immutable payload.
		if _, done := os.Stat(filepath.Join(destination, ".complete")); done == nil {
			return nil
		}
		return err
	}
	return nil
}

func extractFile(entry *zip.File, target string, mode os.FileMode) (err error) {
	src, err := entry.Open()
	if err != nil {
		return err
	}
	defer src.Close()
	dst, err := os.OpenFile(target, os.O_CREATE|os.O_EXCL|os.O_WRONLY, mode)
	if err != nil {
		return err
	}
	_, copyErr := io.Copy(dst, src)
	closeErr := dst.Close()
	if copyErr != nil {
		return copyErr
	}
	return closeErr
}
