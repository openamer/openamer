---
title: doca-flow-grpc-server
description: PLAINTEXT-ONLY: the shipped `doca_flow_grpc` server uses `grpc::InsecureServerCredentials()` with NO TLS / mTLS / token-
---

# doca-flow-grpc-server

**Description:** PLAINTEXT-ONLY: the shipped `doca_flow_grpc` server uses `grpc::InsecureServerCredentials()` with NO TLS / mTLS / token-auth knob on the binary — transport security must come from external infrastructure (e.g. an mTLS proxy / sidecar) on a trusted segment. Use this skill when bringing up, configuring, hardening, or debugging `doca_flow_grpc` — the DOCA-shipped gRPC remote-control surface in front of `doca-flow` that lets non-C++ clients (Python, Go, Rust, Java) program Flow pipes and entries over RPC instead of linking `libdoca_flow.so` directly. Trigger even when the user doesn't say 'doca-flow-grpc-server' or 'gRPC' — e.g. 'program Flow rules from Python on another host', 'remotely configure pipes on the BlueField', 'client times out connecting to the Flow server', 'where is the .proto for Flow', 'UNAUTHENTICATED / FAILED_PRECONDITION on a Flow RPC'. Route elsewhere for the underlying doca-flow API, generic gRPC tooling (protoc, language bindings), or DOCA install / BFB bring-up.

**Lines:** 337 | **Code:** 0 | **Dir:** `doca-flow-grpc-server`

---

---
license: Apache-2.0
name: doca-flow-grpc-server
description: >
  PLAINTEXT-ONLY: the shipped `doca_flow_grpc` server uses
  `grpc::InsecureServerCredentials()` with NO TLS / mTLS / token-auth
  kn...