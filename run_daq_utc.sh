#!/bin/bash

echo "🚀 Avvio DAQ System con timezone UTC forzato"

# Imposta timezone UTC per questo processo
export TZ=UTC

# Ferma eventuali processi DAQ già attivi
pkill -f "python.*main.py" 2>/dev/null
pkill -f "python.*opc_server.py" 2>/dev/null

# Aspetta un momento
sleep 2

echo "🔧 Avvio server OPC UA..."
cd opc_server
TZ=UTC python opc_server.py &
OPC_PID=$!
echo "Server OPC UA avviato (PID: $OPC_PID) con TZ=UTC"

# Attendi che il server sia pronto
sleep 5

echo "📡 Avvio sistema DAQ..."
cd ../daq_system  
TZ=UTC python main.py &
DAQ_PID=$!
echo "Sistema DAQ avviato (PID: $DAQ_PID) con TZ=UTC"

# Salva PID per stop facile
echo $OPC_PID > ../opc_server.pid
echo $DAQ_PID > ../daq_system.pid

cd ..

echo ""
echo "✅ Sistema avviato con timezone UTC!"
echo "📊 I nuovi dati saranno inseriti con timestamp UTC"
echo "🛑 Per fermare: ./stop_system.sh"
