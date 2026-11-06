package main

import (
	"archive/zip"
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCorruptArchiveNeverReportsComplete(t *testing.T) {
	var buffer bytes.Buffer
	writer := zip.NewWriter(&buffer)
	entry, err := writer.CreateHeader(&zip.FileHeader{Name: "node/runtime", Method: zip.Store})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := entry.Write([]byte("runtime-checksum-test")); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	data := buffer.Bytes()
	reader, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		t.Fatal(err)
	}
	offset, err := reader.File[0].DataOffset()
	if err != nil {
		t.Fatal(err)
	}
	data[offset] ^= 1 // Keep the ZIP valid but cause a real CRC verification error.
	dir := t.TempDir()
	log, err := os.Create(filepath.Join(dir, "progress.log"))
	if err != nil {
		t.Fatal(err)
	}
	previous := os.Stderr
	os.Stderr = log
	defer func() { os.Stderr = previous; log.Close() }()
	target := filepath.Join(dir, "runtime", "version")
	if err := unpack(data, target); err == nil {
		t.Fatal("corrupt payload was accepted")
	}
	output, err := os.ReadFile(log.Name())
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(output), "100%") {
		t.Fatal("reported completion after checksum failure")
	}
	if _, err := os.Stat(target); !os.IsNotExist(err) {
		t.Fatal("failed runtime was published")
	}
	stages, err := filepath.Glob(filepath.Join(dir, "runtime", ".extract-*"))
	if err != nil || len(stages) != 0 {
		t.Fatal("partial extraction was not cleaned up")
	}
}

func TestGeneratedFilesNeverOverwriteUserConfig(t *testing.T) {
	dir := t.TempDir()
	runtimeDir, app := filepath.Join(dir, "runtime"), filepath.Join(dir, "app")
	if err := os.MkdirAll(filepath.Join(runtimeDir, "defaults"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(app, 0700); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"config.json", "README.zh-CN.md", "README.en.md"} {
		if err := os.WriteFile(filepath.Join(runtimeDir, "defaults", name), []byte("default"), 0600); err != nil {
			t.Fatal(err)
		}
	}
	t.Setenv("PI_PORTABLE_CONFIG", "")
	config := filepath.Join(app, "config.json")
	if err := ensureDefaultFiles(runtimeDir, app, config); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(config, []byte("user-edited-config"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := ensureDefaultFiles(runtimeDir, app, config); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(config)
	if err != nil || string(data) != "user-edited-config" {
		t.Fatal("existing config was overwritten")
	}
	for _, name := range []string{"README.zh-CN.md", "README.en.md"} {
		if _, err := os.Stat(filepath.Join(app, name)); err != nil {
			t.Fatal(err)
		}
	}
}
