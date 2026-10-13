// mesh-status — Go learning exercise: reimplement `agent-mesh.py status`
// as a fast, single-binary Go CLI.
//
// Reads ~/.openamer/agent-mesh/nodes.json, health-checks each node in
// parallel (goroutines), prints a status table. Exit 0 if all alive nodes
// respond, 1 if any registered node is down (matches Python behaviour of
// reporting problems for cron).
package main

import (
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"
)

type Node struct {
	ID           string   `json:"node_id"`
	Host         string   `json:"host"`
	Port         int      `json:"port"`
	Role         string   `json:"role"`
	Capabilities []string `json:"capabilities"`
	LastSeen     float64  `json:"last_seen"`
	Missed       int      `json:"missed_heartbeats"`
}

type NodeResult struct {
	Node  Node
	Alive bool
	Err   string
}

func loadNodes() ([]Node, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil, err
	}
	path := filepath.Join(home, ".openamer", "agent-mesh", "nodes.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var wrapper map[string]json.RawMessage
	if err := json.Unmarshal(data, &wrapper); err != nil {
		return nil, err
	}
	raw, ok := wrapper["nodes"]
	if !ok {
		// maybe the file is a bare array
		var nodes []Node
		if err := json.Unmarshal(data, &nodes); err != nil {
			return nil, fmt.Errorf("nodes.json: neither {nodes: [...]} nor [...]: %w", err)
		}
		return nodes, nil
	}
	var nodes []Node
	if err := json.Unmarshal(raw, &nodes); err != nil {
		return nil, err
	}
	return nodes, nil
}

func check(n Node) NodeResult {
	res := NodeResult{Node: n}
	client := http.Client{Timeout: 4 * time.Second}
	url := fmt.Sprintf("http://%s:%d/health", n.Host, n.Port)
	resp, err := client.Get(url)
	if err == nil {
		resp.Body.Close()
		res.Alive = resp.StatusCode < 500
		return res
	}
	// HTTP failed — try raw TCP connect as fallback
	conn, derr := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", n.Host, n.Port), 3*time.Second)
	if derr == nil {
		conn.Close()
		res.Alive = true
		res.Err = "tcp-only (no HTTP /health)"
		return res
	}
	res.Err = derr.Error()
	return res
}

func main() {
	nodes, err := loadNodes()
	if err != nil {
		fmt.Fprintf(os.Stderr, "mesh-status: %v\n", err)
		os.Exit(2)
	}

	results := make([]NodeResult, len(nodes))
	var wg sync.WaitGroup
	for i, n := range nodes {
		wg.Add(1)
		go func(i int, n Node) {
			defer wg.Done()
			results[i] = check(n)
		}(i, n)
	}
	wg.Wait()

	sort.Slice(results, func(a, b int) bool {
		if results[a].Alive != results[b].Alive {
			return results[a].Alive // alive first
		}
		return results[a].Node.ID < results[b].Node.ID
	})

	alive := 0
	fmt.Printf("%-22s %-16s %-6s %-8s %-6s %s\n", "NODE", "HOST", "PORT", "ROLE", "ALIVE", "NOTES")
	for _, r := range results {
		mark := "✗"
		note := r.Err
		if r.Alive {
			mark = "✓"
			alive++
		}
		fmt.Printf("%-22s %-16s %-6d %-8s %-6s %s\n",
			r.Node.ID, r.Node.Host, r.Node.Port, r.Node.Role, mark, note)
	}
	fmt.Printf("\nTotal: %d nodes (%d alive)\n", len(nodes), alive)

	if alive < len(nodes) {
		os.Exit(1)
	}
}
