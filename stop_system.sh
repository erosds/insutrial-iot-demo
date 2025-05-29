#!/bin/bash
echo "🛑 Arresto Sistema Industrial IoT"

# Ferma processi Python
if [ -f opc_server.pid ]; then
    OPC_PID=$(cat opc_server.pid)
    echo "Fermando server OPC UA (PID: $OPC_PID)..."
    kill $OPC_PID 2>/dev/null
    rm opc_server.pid
fi

if [ -f daq_system.pid ]; then
    DAQ_PID=$(cat daq_system.pid)
    echo "Fermando sistema DAQ (PID: $DAQ_PID)..."
    kill $DAQ_PID 2>/dev/null
    rm daq_system.pid
fi

# Ferma anche per nome processo (backup)
pkill -f "python.*main.py" 2>/dev/null
pkill -f "python.*opc_server.py" 2>/dev/null

echo "✅ Tutti i processi fermati"
