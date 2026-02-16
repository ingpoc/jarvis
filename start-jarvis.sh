#!/bin/bash
# Jarvis Startup Script - Starts daemon, menu bar app, and tunnel

set -euo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

JARVIS_DIR="/Users/gurusharan/Documents/remote-claude/Codex/jarvis-mac"
JARVIS_HOME="$HOME/.jarvis"
JARVIS_WORKSPACE="/Users/gurusharan/Documents/remote-claude/Jarvisworkspace"
PID_DIR="$JARVIS_HOME/pids"
LOG_DIR="$JARVIS_HOME/logs"
LOCK_FILE="$PID_DIR/start.lock"
DAEMON_LAUNCH_ENV="$JARVIS_HOME/launch.env"
MENUBAR_BIN="$JARVIS_DIR/JarvisApp/.build/debug/JarvisApp"
MENUBAR_LABEL="com.jarvis.menubar"
MENUBAR_AGENT_PLIST="$HOME/Library/LaunchAgents/${MENUBAR_LABEL}.plist"
DAEMON_LABEL="com.jarvis.daemon"
DAEMON_AGENT_PLIST="$HOME/Library/LaunchAgents/${DAEMON_LABEL}.plist"
DAEMON_WRAPPER="$PID_DIR/run_jarvis_daemon.sh"

STARTED_TUNNEL_PID=""
STARTED_DAEMON_PID=""
STARTED_MENUBAR_PID=""
STARTUP_OK=0

# Create directories
mkdir -p "$PID_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$JARVIS_WORKSPACE"

cd "$JARVIS_DIR"

# Prefer project venv python when available so `jarvis` module resolves consistently.
if [ -x "$JARVIS_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$JARVIS_DIR/.venv/bin/python"
else
    PYTHON_BIN="python3"
fi

cleanup_on_error() {
    rm -f "$LOCK_FILE" 2>/dev/null || true
    if [ "$STARTUP_OK" -eq 1 ]; then
        return
    fi
    echo "Startup failed. Cleaning up processes started in this run..."
    for pid in "$STARTED_MENUBAR_PID" "$STARTED_DAEMON_PID" "$STARTED_TUNNEL_PID"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
}

trap cleanup_on_error EXIT

is_pid_alive() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

write_pid() {
    local pid_file="$1"
    local pid="$2"
    echo "$pid" > "$pid_file"
}

safe_kill_pid() {
    local pid="$1"
    if ! is_pid_alive "$pid"; then
        return 0
    fi
    kill "$pid" 2>/dev/null || true
    sleep 1
    if is_pid_alive "$pid"; then
        kill -9 "$pid" 2>/dev/null || true
    fi
}

wait_for_port_listen() {
    local port="$1"
    local timeout_seconds="${2:-15}"
    local elapsed=0
    while [ "$elapsed" -lt "$timeout_seconds" ]; do
        if lsof -n -P -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 1
}

print_failure_log_tail() {
    local log_file="$1"
    local label="$2"
    if [ -f "$log_file" ]; then
        echo -e "${YELLOW}--- Last ${label} log lines ---${NC}"
        tail -n 80 "$log_file" || true
    fi
}

verify_service_started() {
    local service_name="$1"
    local pid="$2"
    local log_file="$3"
    local port="$4"

    if ! is_pid_alive "$pid"; then
        echo "❌ ${service_name} failed: process exited immediately (PID ${pid})"
        print_failure_log_tail "$log_file" "$service_name"
        exit 1
    fi

    if [ -n "$port" ] && ! wait_for_port_listen "$port" 20; then
        echo "❌ ${service_name} failed: port ${port} did not become ready"
        print_failure_log_tail "$log_file" "$service_name"
        exit 1
    fi
}

launchctl_service_pid() {
    local label="$1"
    local gui_domain="gui/$(id -u)"
    launchctl print "$gui_domain/$label" 2>/dev/null | awk -F'= ' '/pid = / {gsub(/;/, "", $2); print $2; exit}'
}

verify_launchctl_service_started() {
    local service_name="$1"
    local service_label="$2"
    local pid_file="$3"
    local log_file="$4"
    local port="$5"
    local timeout_seconds="${6:-25}"
    local elapsed=0
    local pid=""

    while [ "$elapsed" -lt "$timeout_seconds" ]; do
        pid="$(launchctl_service_pid "$service_label" || true)"
        if [ -n "$pid" ] && [ -z "$port" ]; then
            write_pid "$pid_file" "$pid"
            return 0
        fi
        if [ -n "$pid" ] && [ -n "$port" ] && lsof -n -P -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            write_pid "$pid_file" "$pid"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    echo "❌ ${service_name} failed: launchctl service did not become healthy in ${timeout_seconds}s"
    echo "  Last launchctl PID seen: ${pid:-<none>}"
    print_failure_log_tail "$log_file" "$service_name"
    exit 1
}

write_menubar_launch_agent() {
    mkdir -p "$(dirname "$MENUBAR_AGENT_PLIST")"
    cat > "$MENUBAR_AGENT_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$MENUBAR_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$MENUBAR_BIN</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$JARVIS_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/menubar.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/menubar.log</string>
</dict>
</plist>
EOF
}

write_daemon_launch_agent() {
    mkdir -p "$(dirname "$DAEMON_AGENT_PLIST")"
    cat > "$DAEMON_WRAPPER" <<EOF
#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:\${PATH:-}"
if [ -f "$DAEMON_LAUNCH_ENV" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$DAEMON_LAUNCH_ENV" || {
    echo "[daemon-wrapper] FATAL: failed to source $DAEMON_LAUNCH_ENV" >&2
    exit 1
  }
  set +a
else
  echo "[daemon-wrapper] FATAL: missing required launch env: $DAEMON_LAUNCH_ENV" >&2
  exit 1
fi
if [ -f "$JARVIS_HOME/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$JARVIS_HOME/.env" || {
    echo "[daemon-wrapper] FATAL: failed to source $JARVIS_HOME/.env" >&2
    exit 1
  }
  set +a
fi

# Auto-import X bookmarks token from x-content dashboard DB when not explicitly set.
if [ -z "\${X_BOOKMARKS_ACCESS_TOKEN:-}" ] || [ -z "\${X_BOOKMARKS_USER_ID:-}" ]; then
  X_CONTENT_DB="\${X_CONTENT_DB:-\$HOME/Documents/remote-claude/Research/dashboard/prisma/dev.db}"
  if [ -f "\$X_CONTENT_DB" ] && command -v sqlite3 >/dev/null 2>&1; then
    x_row="\$(sqlite3 "\$X_CONTENT_DB" "SELECT COALESCE(xAccessToken,''), COALESCE(xUserId,'') FROM Settings WHERE xAccessToken IS NOT NULL AND xAccessToken <> '' ORDER BY updatedAt DESC LIMIT 1;" 2>/dev/null || true)"
    if [ -n "\$x_row" ]; then
      x_token="\${x_row%%|*}"
      x_user="\${x_row#*|}"
      if [ -n "\$x_token" ] && [ -z "\${X_BOOKMARKS_ACCESS_TOKEN:-}" ]; then
        export X_BOOKMARKS_ACCESS_TOKEN="\$x_token"
      fi
      if [ -n "\$x_user" ] && [ -z "\${X_BOOKMARKS_USER_ID:-}" ]; then
        export X_BOOKMARKS_USER_ID="\$x_user"
      fi
    fi
  fi
fi

exec env PYTHONPATH="$JARVIS_DIR/src\${PYTHONPATH:+:\$PYTHONPATH}" "$PYTHON_BIN" -m jarvis.daemon
EOF
    chmod +x "$DAEMON_WRAPPER"

    cat > "$DAEMON_AGENT_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$DAEMON_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DAEMON_WRAPPER</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$JARVIS_HOME</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/daemon.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/daemon.log</string>
</dict>
</plist>
EOF
}

write_daemon_launch_env() {
    cat > "$DAEMON_LAUNCH_ENV" <<EOF
#!/bin/bash
export JARVIS_WORKSPACE=$(printf '%q' "${JARVIS_WORKSPACE:-}")
export JARVIS_TASK_TIMEOUT_SECS=$(printf '%q' "${JARVIS_TASK_TIMEOUT_SECS:-}")
export JARVIS_STALE_TASK_SECS=$(printf '%q' "${JARVIS_STALE_TASK_SECS:-}")
export ANTHROPIC_DEFAULT_OPUS_MODEL=$(printf '%q' "${ANTHROPIC_DEFAULT_OPUS_MODEL:-}")
export ANTHROPIC_DEFAULT_SONNET_MODEL=$(printf '%q' "${ANTHROPIC_DEFAULT_SONNET_MODEL:-}")
export ANTHROPIC_DEFAULT_HAIKU_MODEL=$(printf '%q' "${ANTHROPIC_DEFAULT_HAIKU_MODEL:-}")
export ANTHROPIC_BASE_URL=$(printf '%q' "${ANTHROPIC_BASE_URL:-}")
export ANTHROPIC_AUTH_TOKEN=$(printf '%q' "${ANTHROPIC_AUTH_TOKEN:-}")
export ANTHROPIC_API_KEY=$(printf '%q' "${ANTHROPIC_API_KEY:-}")
export CLAUDE_CODE_OAUTH_TOKEN=$(printf '%q' "${CLAUDE_CODE_OAUTH_TOKEN:-}")
export JARVIS_SLACK_BOT_TOKEN=$(printf '%q' "${JARVIS_SLACK_BOT_TOKEN:-}")
export JARVIS_SLACK_APP_TOKEN=$(printf '%q' "${JARVIS_SLACK_APP_TOKEN:-}")
export JARVIS_API_TOKEN=$(printf '%q' "${JARVIS_API_TOKEN:-}")
export ELEVENLABS_API_KEY=$(printf '%q' "${ELEVENLABS_API_KEY:-}")
export ELEVENLABS_AGENT_ID=$(printf '%q' "${ELEVENLABS_AGENT_ID:-}")
export X_BOOKMARKS_ACCESS_TOKEN=$(printf '%q' "${X_BOOKMARKS_ACCESS_TOKEN:-}")
export X_BOOKMARKS_USER_ID=$(printf '%q' "${X_BOOKMARKS_USER_ID:-}")
EOF
    chmod 600 "$DAEMON_LAUNCH_ENV"
}

start_daemon_with_launchctl() {
    write_daemon_launch_agent
    local gui_domain="gui/$(id -u)"

    launchctl bootout "$gui_domain/$DAEMON_LABEL" >/dev/null 2>&1 || true
    local bootstrap_err=""
    if ! bootstrap_err="$(launchctl bootstrap "$gui_domain" "$DAEMON_AGENT_PLIST" 2>&1)"; then
        echo "⚠️  Daemon bootstrap reported error: $bootstrap_err"
        echo "    Attempting kickstart of existing daemon service..."
    fi
    launchctl kickstart -k "$gui_domain/$DAEMON_LABEL" >/dev/null 2>&1 || true

    local pid
    pid="$(launchctl print "$gui_domain/$DAEMON_LABEL" 2>/dev/null | awk -F'= ' '/pid = / {gsub(/;/, "", $2); print $2; exit}')"
    if [ -n "${pid:-}" ]; then
        write_pid "$PID_DIR/daemon.pid" "$pid"
        echo "  Daemon PID: $pid"
        STARTED_DAEMON_PID="$pid"
    else
        echo "❌ Daemon failed: launchctl did not report a running PID"
        if [ -n "$bootstrap_err" ]; then
            echo "Bootstrap error: $bootstrap_err"
        fi
        print_failure_log_tail "$LOG_DIR/daemon.log" "Daemon"
        exit 1
    fi
}

start_menubar_with_launchctl() {
    write_menubar_launch_agent
    local gui_domain="gui/$(id -u)"

    launchctl bootout "$gui_domain/$MENUBAR_LABEL" >/dev/null 2>&1 || true
    local bootstrap_err=""
    if ! bootstrap_err="$(launchctl bootstrap "$gui_domain" "$MENUBAR_AGENT_PLIST" 2>&1)"; then
        echo "⚠️  Menu bar bootstrap reported error: $bootstrap_err"
        echo "    Attempting kickstart of existing menu bar service..."
    fi
    launchctl kickstart -k "$gui_domain/$MENUBAR_LABEL" >/dev/null 2>&1 || true

    local pid
    pid="$(launchctl print "$gui_domain/$MENUBAR_LABEL" 2>/dev/null | awk -F'= ' '/pid = / {gsub(/;/, "", $2); print $2; exit}')"
    if [ -n "${pid:-}" ]; then
        write_pid "$PID_DIR/menubar.pid" "$pid"
        echo "  Menu bar PID: $pid"
        STARTED_MENUBAR_PID="$pid"
    else
        echo "❌ Menu bar app failed: launchctl did not report a running PID"
        if [ -n "$bootstrap_err" ]; then
            echo "Bootstrap error: $bootstrap_err"
        fi
        print_failure_log_tail "$LOG_DIR/menubar.log" "Menu bar app"
        exit 1
    fi
}

echo -e "${BLUE}=== Jarvis Startup ===${NC}"
echo ""

mkdir -p "$PID_DIR" "$LOG_DIR"
if [ -e "$LOCK_FILE" ]; then
    existing_lock_pid="$(cat "$LOCK_FILE" 2>/dev/null || true)"
    if [ -n "$existing_lock_pid" ] && is_pid_alive "$existing_lock_pid"; then
        echo "Another startup is already in progress (PID: $existing_lock_pid)"
        exit 1
    fi
fi
write_pid "$LOCK_FILE" "$$"

# Kill any processes on our ports first
echo -e "${YELLOW}◆ Checking for existing processes on ports 9847, 9848...${NC}"
for port in 9847 9848; do
    PID=$(lsof -tiTCP:$port -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo -e "${YELLOW}  Killing process on port $port (PID: $PID)${NC}"
        for p in $PID; do
            safe_kill_pid "$p"
        done
    fi
done

# Load environment variables
if [ -f "$JARVIS_HOME/.env" ]; then
    # shellcheck disable=SC1090
    set -a
    source "$JARVIS_HOME/.env"
    set +a
fi
if [ -f "$JARVIS_DIR/.env" ]; then
    # shellcheck disable=SC1090
    set -a
    source "$JARVIS_DIR/.env"
    set +a
fi

export JARVIS_API_TOKEN="${JARVIS_API_TOKEN:-jarvis-voice-token}"
export ELEVENLABS_API_KEY="${ELEVENLABS_API_KEY:-}"
export ELEVENLABS_AGENT_ID="${ELEVENLABS_AGENT_ID:-}"
export ANTHROPIC_DEFAULT_OPUS_MODEL="${ANTHROPIC_DEFAULT_OPUS_MODEL:-glm-4.7}"
export ANTHROPIC_DEFAULT_SONNET_MODEL="${ANTHROPIC_DEFAULT_SONNET_MODEL:-glm-4.7}"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="${ANTHROPIC_DEFAULT_HAIKU_MODEL:-glm-4.7}"
export JARVIS_ENABLE_TUNNEL="${JARVIS_ENABLE_TUNNEL:-0}"
# Container system (Apple `container` CLI) is a hard dependency for containerized workflows.
# Keep it explicit and fail-fast: if required and not running, try to start it; if that fails, abort.
export JARVIS_REQUIRE_CONTAINERS="${JARVIS_REQUIRE_CONTAINERS:-1}"

# Task runtime watchdog:
# - unset/empty: unbounded (no timeout)
# - <= 0: unbounded (no timeout)
# - > 0: seconds
export JARVIS_TASK_TIMEOUT_SECS="${JARVIS_TASK_TIMEOUT_SECS:-0}"

# Stale-task recovery watchdog (used only by the idle-autonomy scheduler):
# - <= 0: disabled
# - > 0: seconds since last update to consider in_progress tasks abandoned
export JARVIS_STALE_TASK_SECS="${JARVIS_STALE_TASK_SECS:-0}"

# Ensure container system is running (if required).
if [ "$JARVIS_REQUIRE_CONTAINERS" = "1" ]; then
    if ! command -v container >/dev/null 2>&1; then
        echo -e "${RED}FATAL: 'container' CLI not found in PATH.${NC}"
        echo -e "${RED}       Install Apple container tooling or set JARVIS_REQUIRE_CONTAINERS=0.${NC}"
        exit 1
    fi

    if ! container system status 2>/dev/null | grep -q "apiserver is running"; then
        echo -e "${YELLOW}◆ Apple container system not running; starting it now...${NC}"
        if ! container system start >> "$LOG_DIR/daemon.log" 2>&1; then
            echo -e "${RED}FATAL: Failed to start container system (see $LOG_DIR/daemon.log).${NC}"
            exit 1
        fi

        # Wait until apiserver reports running (give it time to register with launchd).
        tries=0
        while [ "$tries" -lt 60 ]; do
            if container system status 2>/dev/null | grep -q "apiserver is running"; then
                break
            fi
            tries=$((tries + 1))
            sleep 2
        done

        if ! container system status 2>/dev/null | grep -q "apiserver is running"; then
            echo -e "${RED}FATAL: Container system did not become healthy (apiserver not running).${NC}"
            echo -e "${RED}       Try running: container system start${NC}"
            exit 1
        fi
    fi
fi

# Persist launch-safe environment snapshot under ~/.jarvis so launchd jobs
# don't require Files & Folders access to the project path under Documents.
write_daemon_launch_env

# Check if already running
if [ "$JARVIS_ENABLE_TUNNEL" = "1" ]; then
    if [ -f "$PID_DIR/tunnel.pid" ] && is_pid_alive "$(cat "$PID_DIR/tunnel.pid")"; then
        echo -e "${YELLOW}⚠️  Tunnel already running (PID: $(cat "$PID_DIR/tunnel.pid"))${NC}"
    else
        # Start localtunnel for webhooks
        echo -e "${GREEN}▶ Starting tunnel on port 9848...${NC}"
        nohup npx localtunnel --port 9848 --subdomain jarvis-voice \
            > "$LOG_DIR/tunnel.log" 2>&1 &
        TUNNEL_PID=$!
        STARTED_TUNNEL_PID="$TUNNEL_PID"
        write_pid "$PID_DIR/tunnel.pid" "$TUNNEL_PID"
        echo "  Tunnel PID: $TUNNEL_PID"
        sleep 2
        verify_service_started "Tunnel" "$TUNNEL_PID" "$LOG_DIR/tunnel.log" ""
    fi
else
    echo -e "${BLUE}◆ Tunnel startup disabled (set JARVIS_ENABLE_TUNNEL=1 to enable)${NC}"
fi

if [ -f "$PID_DIR/daemon.pid" ] && is_pid_alive "$(cat "$PID_DIR/daemon.pid")"; then
    echo -e "${YELLOW}⚠️  Daemon already running (PID: $(cat "$PID_DIR/daemon.pid"))${NC}"
else
    # Start Jarvis daemon in background
    echo -e "${GREEN}▶ Starting Jarvis daemon...${NC}"
    cd "$JARVIS_DIR"
    start_daemon_with_launchctl
    verify_launchctl_service_started "Daemon" "$DAEMON_LABEL" "$PID_DIR/daemon.pid" "$LOG_DIR/daemon.log" "9847" "30"
fi

if [ -f "$PID_DIR/menubar.pid" ] && is_pid_alive "$(cat "$PID_DIR/menubar.pid")"; then
    echo -e "${YELLOW}⚠️  Menu bar already running (PID: $(cat "$PID_DIR/menubar.pid"))${NC}"
else
    # Start menu bar app
    echo -e "${GREEN}▶ Starting menu bar app...${NC}"
    # Always build before launching so UI changes are picked up (incremental build is fast).
    swift build --package-path JarvisApp >> "$LOG_DIR/menubar.log" 2>&1
    start_menubar_with_launchctl
    verify_launchctl_service_started "Menu bar app" "$MENUBAR_LABEL" "$PID_DIR/menubar.pid" "$LOG_DIR/menubar.log" "" "30"
fi

echo ""
echo -e "${GREEN}✓ Jarvis is running!${NC}"
echo ""

# Open log viewer terminal only when explicitly enabled.
if [ "${JARVIS_OPEN_LOG_VIEWER:-0}" != "1" ]; then
    echo -e "${BLUE}◆ Log viewer auto-open disabled (set JARVIS_OPEN_LOG_VIEWER=1 to enable)${NC}"
else
    echo -e "${BLUE}◆ Opening log viewer terminal...${NC}"

# Create a script for the log viewer terminal
cat > "$PID_DIR/log_viewer.sh" << 'EOF'
#!/bin/bash
LOG_DIR="$HOME/.jarvis/logs"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}=== Jarvis Log Viewer ===${NC}"
echo -e "${YELLOW}Press Ctrl+C to close log viewer (Jarvis continues running)${NC}"
echo ""

# Use temp files to track line counts (bash 3.2 compatible)
COUNT_DIR="$HOME/.jarvis/pids"
mkdir -p "$COUNT_DIR"
daemon_count_file="$COUNT_DIR/daemon_lines.count"
menubar_count_file="$COUNT_DIR/menubar_lines.count"
tunnel_count_file="$COUNT_DIR/tunnel_lines.count"

# Function to get/set line count
get_count() { cat "$1" 2>/dev/null || echo 0; }
set_count() { echo "$1" > "$2"; }

# Function to color output
color_line() {
    local line="$1"
    local log_name="$2"
    if echo "$line" | grep -qi "error\|exception\|failed\|fatal"; then
        echo -e "${RED}[${log_name}]${NC} $line"
    elif echo "$line" | grep -qi "warn\|warning"; then
        echo -e "${YELLOW}[${log_name}]${NC} $line"
    elif echo "$line" | grep -qi "info"; then
        echo -e "${GREEN}[${log_name}]${NC} $line"
    elif echo "$line" | grep -qi "task.*complete\|success\|finished"; then
        echo -e "${CYAN}[${log_name}]${NC} $line"
    elif echo "$line" | grep -qi "task.*start\|starting\|running"; then
        echo -e "${BLUE}[${log_name}]${NC} $line"
    else
        echo -e "[${log_name}] $line"
    fi
}

# Show existing content
echo -e "${BLUE}--- Existing log content ---${NC}"
for log_name in daemon menubar tunnel; do
    log_file="$LOG_DIR/${log_name}.log"
    if [ -f "$log_file" ]; then
        lines=$(wc -l < "$log_file" 2>/dev/null || echo 0)
        if [ "$lines" -gt 0 ]; then
            echo -e "${BLUE}>>> ${log_name}.log (${lines} lines) <<<${NC}"
            while IFS= read -r line; do
                color_line "$line" "${log_name}"
            done < "$log_file"
            # Save initial count
            set_count "$lines" "$COUNT_DIR/${log_name}_lines.count"
        fi
    fi
done

echo -e "${BLUE}--- Monitoring for new logs (Ctrl+C to stop) ---${NC}"
echo ""

# Monitor loop
while true; do
    for log_name in daemon menubar tunnel; do
        log_file="$LOG_DIR/${log_name}.log"
        count_file="$COUNT_DIR/${log_name}_lines.count"

        if [ -f "$log_file" ]; then
            current_lines=$(wc -l < "$log_file")
            old_lines=$(get_count "$count_file")

            if [ "$current_lines" -gt "$old_lines" ]; then
                # Show new lines
                tail -n +"$((old_lines + 1))" "$log_file" 2>/dev/null | while IFS= read -r line; do
                    color_line "$line" "${log_name}"
                done
                set_count "$current_lines" "$count_file"
            fi
        fi
    done
    sleep 0.5
done
EOF

chmod +x "$PID_DIR/log_viewer.sh"

    # Open a single Terminal log viewer instance (avoid duplicate tabs/windows)
    if pgrep -f "bash $PID_DIR/log_viewer.sh" >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Log viewer already running; reusing existing terminal${NC}"
    elif command -v osascript >/dev/null 2>&1; then
        osascript << EOF
tell application "Terminal"
    activate
    set newTab to do script "bash $PID_DIR/log_viewer.sh"
    set custom title of newTab to "Jarvis Logs"
end tell
EOF
    else
        echo -e "${YELLOW}⚠️  osascript not available; skipping log viewer terminal auto-open${NC}"
    fi
fi

sleep 1

echo ""
echo "Logs: $LOG_DIR/"
echo "To stop: ./stop-jarvis.sh"

STARTUP_OK=1
rm -f "$LOCK_FILE"
