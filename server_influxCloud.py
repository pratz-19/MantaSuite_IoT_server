import flask as fl
from flask import request, jsonify
import struct
import base64
import time
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# InfluxDB setup
TOKEN = "kGL8NmhCSDV4PcDj6pP6VukywxEJosWNULmXy5SL4XNpi3ZJxByWD2GRNjUyK_5h44SzDu-ViNlf8ymog1f3rg=="
ORG = "SeaSpark"
BUCKET = "ocean-data"
URL = "https://us-east-1-1.aws.cloud2.influxdata.com"

influx_client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

def computeChecksum(packet):
    checksum = 0
    for i in range(4, len(packet)):
        checksum = (checksum + struct.unpack('<B', packet[i:i+1])[0]) % 65536
    return checksum

def decodePacket(packet):
    print("Currently Decoding...")
    print("Length:", len(packet))
    decodedPacket = {}
    decodedPacket['packet_type'] = struct.unpack('<B', packet[0:1])[0]
    decodedPacket['sample_count'] = struct.unpack('<B', packet[1:2])[0]
    decodedPacket['checksum'] = struct.unpack('>H', packet[2:4])[0]

    if decodedPacket['checksum'] != computeChecksum(packet):
        raise Exception("Checksum mismatch")

    if decodedPacket['packet_type'] == 0:
        decodedPacket['samples'] = []
        for i in range(decodedPacket['sample_count']):
            base = 4 + i * 40  # 40 bytes per sample now
            sample = {
                'sample_timestamp': struct.unpack('>H', packet[base+0:base+2])[0],
                'temperature1': struct.unpack('>h', packet[base+2:base+4])[0] / 256,
                'humidity1': struct.unpack('>H', packet[base+4:base+6])[0] / 512,
                'temperature2': struct.unpack('>h', packet[base+6:base+8])[0] / 256,
                'humidity2': struct.unpack('>H', packet[base+8:base+10])[0] / 512,
                'temperature3': struct.unpack('>h', packet[base+10:base+12])[0] / 256,
                'humidity3': struct.unpack('>H', packet[base+12:base+14])[0] / 512,
                'pH': struct.unpack('>B', packet[base+14:base+15])[0] / 20,
                'tds': struct.unpack('>H', packet[base+15:base+17])[0],
                'water_flags': struct.unpack('>B', packet[base+17:base+18])[0],
                'v_load': struct.unpack('>H', packet[base+18:base+20])[0],
                'i_load': struct.unpack('>H', packet[base+20:base+22])[0],
                'v_gen1': struct.unpack('>H', packet[base+22:base+24])[0],
                'i_gen1': struct.unpack('>H', packet[base+24:base+26])[0],
                'v_gen2': struct.unpack('>H', packet[base+26:base+28])[0],
                'i_gen2': struct.unpack('>H', packet[base+28:base+30])[0],
                'v_gen3': struct.unpack('>H', packet[base+30:base+32])[0],
                'i_gen3': struct.unpack('>H', packet[base+32:base+34])[0]
            }
            decodedPacket['samples'].append(sample)

    else:
        raise Exception("Unsupported packet type")

    print("Decoding Success!")
    return decodedPacket

app = fl.Flask(__name__)

@app.route('/iridiun-data', methods=['POST'])
def receive_iridiun_data():
    try:
        print("\n--- Incoming Request ---")
        form_data = request.form.to_dict()
        print("Parsed Form Data:", form_data)

        decodedPacket = decodePacket(bytearray.fromhex(form_data['data']))
        print("Decoded Packet:", decodedPacket)

        # Push to InfluxDB for packet type 0 
        if decodedPacket['packet_type'] == 0:
            for sample in decodedPacket['samples']:
                point = (
                    Point("sensor_data")
                    .field("temperature1", sample['temperature1'])
                    .field("humidity1", sample['humidity1'])
                    .field("temperature2", sample['temperature2'])
                    .field("humidity2", sample['humidity2'])
                    .field("temperature3", sample['temperature3'])
                    .field("humidity3", sample['humidity3'])
                    .field("pH", sample['pH'])
                    .field("tds", sample['tds'])
                    .field("water_flags", sample['water_flags'])
                    .field("v_load", sample['v_load'])
                    .field("i_load", sample['i_load'])
                    .field("v_gen1", sample['v_gen1'])
                    .field("i_gen1", sample['i_gen1'])
                    .field("v_gen2", sample['v_gen2'])
                    .field("i_gen2", sample['i_gen2'])
                    .field("v_gen3", sample['v_gen3'])
                    .field("i_gen3", sample['i_gen3'])
                    .time(time.time_ns(), WritePrecision.NS)
                )
                write_api.write(bucket=BUCKET, org=ORG, record=point)

        return jsonify({"status": "success", "data": decodedPacket}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "failure", "error": str(e)}), 200

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        print("⚠️ Received unexpected POST to '/' — maybe update RockBLOCK target?")
        return "Use /iridiun-data instead", 200
    return "<h1>Welcome to the Iridium Data Server</h1>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)
