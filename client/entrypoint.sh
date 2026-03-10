#!/bin/bash
cd /app

PASSWORD_FILE="/home/divinemesh/.divinemesh/password.txt"

if [ ! -f "$PASSWORD_FILE" ]; then
    echo "First run — registering node..."
    OUTPUT=$(python -m client.daemon register 2>&1)
    echo "$OUTPUT"
    PASSWORD=$(echo "$OUTPUT" | grep -A1 "AUTO-GENERATED PASSWORD" | tail -1 | xargs)
    echo "$PASSWORD" > "$PASSWORD_FILE"
    chmod 600 "$PASSWORD_FILE"
    echo "Password saved."
else
    PASSWORD=$(cat "$PASSWORD_FILE")
    echo "Identity found — using saved password."
fi

echo "Starting daemon..."
python -m client.daemon start --password "$PASSWORD" &

echo "Daemon running! Keeping container alive..."
tail -f /dev/null
