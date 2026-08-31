// mesh-daemon — Phase 3 Go daemon: resident mesh supervisor.
//
// Replaces the Python service-watchdog's mesh-related duties with a single
// always-on binary (target: ~10 MB RSS vs ~35 MB Python):
//   - runs/monitors the agent-mesh master node health (HTTP probe)
//   - exposes its own /health + /status endpoint on :18920
//   - writes a status JSON for cron consumption
//
// Usage: mesh-daemon [-addr :18920] [-mesh http://127.0.0.1:8900] [-interval 30s]
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"sync"
	"time"
)

type Status struct {
	UpdatedAt string `json:"updated_at"`
	MeshURL   string `json:"mesh_url"`
	MeshAlive bool   `json:"mesh_alive"`
	MeshErr   string `json:"mesh_error,omitempty"`
	UptimeSec int64  `json:"uptime_sec"`
	GoVersion string `json:"go_version"`
	Goroutines int   `json:"goroutines"`
	MemAllocMB float64 `json:"mem_alloc_mb"`
}

var (
	status   Status
	statusMu sync.RWMutex
	start    = time.Now()
	meshURL  string
)

func probeMesh(url string) (bool, string) {
	client := http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(url + "/health")
	if err != nil {
		return false, err.Error()
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 500 {
		return false, fmt.Sprintf("HTTP %d", resp.StatusCode)
	}
	return true, ""
}

func monitor(interval time.Duration) {
	for {
		alive, errMsg := probeMesh(meshURL)
		var ms runtime.MemStats
		runtime.ReadMemStats(&ms)
		statusMu.Lock()
		status.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
		status.MeshAlive = alive
		status.MeshErr = errMsg
		status.UptimeSec = int64(time.Since(start).Seconds())
		status.GoVersion = runtime.Version()
		status.Goroutines = runtime.NumGoroutine()
		status.MemAllocMB = float64(ms.Alloc) / 1024 / 1024
		statusMu.Unlock()
		time.Sleep(interval)
	}
}

func writeStatusFile() {
	home, err := os.UserHomeDir()
	if err != nil {
		return
	}
	path := filepath.Join(home, ".openamer", "mesh-daemon-status.json")
	statusMu.RLock()
	data, _ := json.MarshalIndent(status, "", "  ")
	statusMu.RUnlock()
	_ = os.WriteFile(path, data, 0o644)
}

func main() {
	addr := flag.String("addr", ":18920", "listen address for health endpoint")
	mesh := flag.String("mesh", "http://127.0.0.1:8900", "mesh master URL")
	interval := flag.Duration("interval", 30*time.Second, "probe interval")
	flag.Parse()
	meshURL = *mesh

	status.MeshURL = *mesh

	go monitor(*interval)

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		statusMu.RLock()
		defer statusMu.RUnlock()
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(status)
	})
	http.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
		writeStatusFile()
		http.Redirect(w, r, "/health", http.StatusTemporaryRedirect)
	})

	log.Printf("mesh-daemon: listening on %s, probing mesh at %s every %s",
		*addr, *mesh, *interval)
	if err := http.ListenAndServe(*addr, nil); err != nil {
		log.Fatalf("mesh-daemon: %v", err)
	}
}
