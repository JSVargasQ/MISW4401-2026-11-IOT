import ssl
from django.db.models import Avg
from datetime import timedelta, datetime
from django.utils import timezone
from receiver.models import Data, Measurement
import paho.mqtt.client as mqtt
import schedule
import time
from django.conf import settings

client = mqtt.Client(settings.MQTT_USER_PUB)


def analyze_data():
    # Consulta datos recientes, los agrupa por estación y variable y compara con límites.
    # En el modelo Data, 'time' y 'base_time' tienen precisión por HORA (se truncan en create_data).
    # Por eso filtramos por base_time en las últimas 2 horas para tener datos recientes.

    print("Calculando alertas...")
    now = timezone.now()
    window_start = (now - timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)

    raw = Data.objects.filter(base_time__gte=window_start)
    aggregation = raw.values(
        'station__user__username',
        'station__location__city__name',
        'station__location__state__name',
        'station__location__country__name',
        'measurement__name',
        'measurement__max_value',
        'measurement__min_value',
    ).annotate(check_value=Avg('avg_value'))
    print("Datos en ventana (últimas 2 h):", raw.count(), "| Grupos (estación+variable):", len(aggregation))
    SUPER_OFFSET = 2  # puntos por encima del máximo para alerta super máxima
    alerts = 0
    for item in aggregation:
        variable = item["measurement__name"]
        max_value = item["measurement__max_value"] or 0
        min_value = item["measurement__min_value"] or 0
        check_value = item["check_value"]

        country = item['station__location__country__name']
        state = item['station__location__state__name']
        city = item['station__location__city__name']
        user = item['station__user__username']
        topic = '{}/{}/{}/{}/in'.format(country, state, city, user)

        if check_value > max_value + SUPER_OFFSET:
            if variable.lower() == 'temperatura':
                message = "ALERT {} {} {}".format(variable, min_value, max_value)
                print(datetime.now(), "Sending alert to {} {}".format(topic, variable))
                client.publish(topic, message)
                alerts += 1
            message = "ALERT_SUPER {} {} {} (>{})".format(
                variable, min_value, max_value, max_value + SUPER_OFFSET)
            print(datetime.now(), "Sending super alert to {} {}".format(topic, variable))
            client.publish(topic, message)
            alerts += 1
        elif check_value > max_value or check_value < min_value:
            message = "ALERT {} {} {}".format(variable, min_value, max_value)
            print(datetime.now(), "Sending alert to {} {}".format(topic, variable))
            client.publish(topic, message)
            alerts += 1

    print(len(aggregation), "dispositivos revisados")
    print(alerts, "alertas enviadas")


def on_connect(client, userdata, flags, rc):
    '''
    Función que se ejecuta cuando se conecta al bróker.
    '''
    print("Conectando al broker MQTT...", mqtt.connack_string(rc))


def on_disconnect(client: mqtt.Client, userdata, rc):
    '''
    Función que se ejecuta cuando se desconecta del broker.
    Intenta reconectar al bróker.
    '''
    print("Desconectado con mensaje:" + str(mqtt.connack_string(rc)))
    print("Reconectando...")
    client.reconnect()


def setup_mqtt():
    '''
    Configura el cliente MQTT para conectarse al broker.
    '''

    print("Iniciando cliente MQTT...", settings.MQTT_HOST, settings.MQTT_PORT)
    global client
    try:
        client = mqtt.Client(settings.MQTT_USER_PUB)
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect

        if settings.MQTT_USE_TLS:
            client.tls_set(ca_certs=settings.CA_CRT_PATH,
                           tls_version=ssl.PROTOCOL_TLSv1_2, cert_reqs=ssl.CERT_NONE)

        client.username_pw_set(settings.MQTT_USER_PUB,
                               settings.MQTT_PASSWORD_PUB)
        client.connect(settings.MQTT_HOST, settings.MQTT_PORT)

    except Exception as e:
        print('Ocurrió un error al conectar con el bróker MQTT:', e)


def start_cron():
    '''
    Inicia el cron que se encarga de ejecutar la función analyze_data cada 1 minuto.
    '''
    print("Iniciando cron...")
    schedule.every(1).minutes.do(analyze_data)
    print("Servicio de control iniciado")
    while 1:
        schedule.run_pending()
        time.sleep(1)
