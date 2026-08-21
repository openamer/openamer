#!/bin/bash
# openamer-stealth.sh — Stealth Browser Service Manager
# Startet/Stoppt/Prüft den Stealth-Browser-Server
# 
# Usage: ./openamer-stealth.sh start|stop|status|connect

STEALTH_DIR="/c/Users/damir/AppData/Local/openamer-laptop/stealth"
SCRIPT="$STEALTH_DIR/../scripts/stealth-server.mjs"
LOCK="$STEALTH_DIR/browser.lock"
LOG="$STEALTH_DIR/server.log"

start() {
    if [ -f "$LOCK" ]; then
        PID=$(cat "$LOCK" | node -e "process.stdin.on('data',d=>{try{console.log(JSON.parse(d).pid)}catch(e){console.log('0')}})")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "✅ Stealth Server läuft bereits (PID $PID)"
            cat "$LOCK" | node -e "process.stdin.on('data',d=>{try{console.log('🔗',JSON.parse(d).wsEndpoint)}catch(e){}})"
            return
        fi
        rm -f "$LOCK"
    fi
    
    echo "🔄 Starte Stealth Server..."
    cd "$STEALTH_DIR/../scripts"
    nohup node stealth-server.mjs > "$LOG" 2>&1 &
    
    # Warte auf Start
    for i in $(seq 1 15); do
        sleep 1
        if [ -f "$LOCK" ]; then
            WS=$(cat "$LOCK" | node -e "process.stdin.on('data',d=>{try{console.log(JSON.parse(d).wsEndpoint)}catch(e){}})")
            echo "✅ Stealth Server gestartet"
            echo "🔗 $WS"
            echo "📋 agent-browser connect $WS"
            return
        fi
    done
    echo "❌ Start fehlgeschlagen. Log: $LOG"
    tail -5 "$LOG"
}

stop() {
    if [ -f "$LOCK" ]; then
        PID=$(cat "$LOCK" | node -e "process.stdin.on('data',d=>{try{console.log(JSON.parse(d).pid)}catch(e){console.log('0')}})")
        if [ "$PID" != "0" ]; then
            kill "$PID" 2>/dev/null
        fi
        rm -f "$LOCK"
        echo "✅ Stealth Server gestoppt"
    else
        echo "⚠ Kein aktiver Server"
    fi
}

status() {
    if [ -f "$LOCK" ]; then
        cat "$LOCK" | node -e "
            process.stdin.on('data', d => {
                try {
                    const j = JSON.parse(d);
                    const running = (() => { try { process.kill(j.pid, 0); return true; } catch(e) { return false; } })();
                    console.log('PID:', j.pid, '| Running:', running);
                    console.log('WS:', j.wsEndpoint);
                } catch(e) { console.log('Lock invalid'); }
            });
        "
    else
        echo "⚠ Kein aktiver Server"
    fi
}

connect() {
    if [ ! -f "$LOCK" ]; then
        echo "⚠ Stealth Server läuft nicht. Starte ihn zuerst."
        start
    fi
    WS=$(cat "$LOCK" | node -e "process.stdin.on('data',d=>{try{console.log(JSON.parse(d).wsEndpoint)}catch(e){}})")
    echo "🔄 Verbinde agent-browser..."
    agent-browser connect "$WS"
}

case "${1:-start}" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    connect) connect ;;
    restart) stop; sleep 1; start ;;
    *) echo "Usage: $0 {start|stop|status|connect|restart}" ;;
esac