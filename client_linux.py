import serial
import socket
import threading
import time

VIRTUAL_SERIAL = '/dev/cot0'  # 虚拟串口路径
BAUDRATE = 9600               # 串口波特率
SERVER_IP = '192.168.0.27'    # Windows服务器IP
SERVER_PORT = 4000            # 端口

REFRESH_RATE = 30 # 刷新率（帧/秒）

def serial_to_socket(ser, sock):
    """串口到网络数据转发线程"""
    interval = 1.0/REFRESH_RATE
    while True:
        try:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
                if data:
                    sock.sendall(data)
            time.sleep(interval)  # 控制发送频率
        except Exception as e:
            print(f"串口到网络异常: {e}")
            break

def socket_to_serial(ser, sock):
    """网络到串口数据转发线程"""
    while True:
        try:
            data = sock.recv(1024)
            if data:
                ser.write(data)
            else:
                print("服务器关闭了连接")
                break
        except Exception as e:
            print(f"网络到串口异常: {e}")
            break

def connect_and_run():
    """连接服务器并启动收发线程，断线后返回"""
    try:
        ser = serial.Serial(VIRTUAL_SERIAL, BAUDRATE, timeout=0)
    except Exception as e:
        print(f"打开串口失败: {e}")
        return False

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((SERVER_IP, SERVER_PORT))
        print("已连接到服务器")
    except Exception as e:
        print(f"连接服务器失败: {e}")
        ser.close()
        sock.close()
        return False

    t1 = threading.Thread(target=serial_to_socket, args=(ser, sock), daemon=True)
    t2 = threading.Thread(target=socket_to_serial, args=(ser, sock), daemon=True)
    t1.start()
    t2.start()

    try:
        while t1.is_alive() and t2.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("手动退出")
    finally:
        ser.close()
        sock.close()
    return True

def main():
    print("客户端启动，准备连接服务器...")
    while True:
        success = connect_and_run()
        if not success:
            print("等待1分钟后重试连接...")
            time.sleep(60)  # 每分钟重连一次
        else:
            print("连接断开，1分钟后重试...")
            time.sleep(60)

if __name__ == '__main__':
    main()