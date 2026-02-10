# --- INICIALIZACIÓN ---
set ant 999
set ite 0
# Configuramos la batería inicial en 100 Joules
battery set 100
atget id id
getpos2 lonSen latSen

# --- BUCLE PRINCIPAL ---
loop
# 1. Control de iteraciones
inc ite
print ite
if (ite >= 1000)
    stop
end

# 2. Lectura de mensajes
wait 10
read mens
rdata mens tipo valor valor2

# 3. Lógica de enrutamiento (Routing)
if((tipo=="hola") && (ant == 999))
   set ant valor
   data mens tipo id
   send mens * valor
end

if(tipo=="alerta")
   # Reenvía la alerta al nodo anterior (camino a la base)
   send mens ant
end

if (tipo=="stop")
    # Propaga la orden de parada
    data mens "stop"
    send mens * valor
    cprint "Parada recibida. Sensor: " id
    wait 1000
    stop
end

if (tipo=="critico")
    # Reenvía mensaje de batería crítica
    send mens ant
end

# 4. Sensado y Lógica de Batería
# Consumo de tiempo (simula 10ms entre lecturas o acciones)
delay 10

# Chequeo de nivel de batería
battery bat
if(bat < 5)
    data mens "critico" lonSen latSen
    send mens ant
end

# Lectura del sensor físico
areadsensor tempSen
rdata tempSen SensTipo idSens temp

if( temp > 30)
   data mens "alerta" lonSen latSen
   send mens ant
end