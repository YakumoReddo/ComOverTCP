import serial
import socket
import threading
import time
import struct  # 用于打包/解包序号和长度

VIRTUAL_SERIAL = '/dev/cot0'  # 虚拟串口路径
BAUDRATE = 9600               # 串口波特率
SERVER_IP = '192.168.0.27'    # Windows服务器IP
SERVER_PORT = 4000            # 端口

REFRESH_RATE = 30 # 刷新率（帧/秒）

def serial_to_socket(ser, sock):
    """串口到网络数据转发线程，增加包头（序号和长度）"""
    interval = 1.0 / REFRESH_RATE
    seq = 0  # 包序号
    while True:
        try:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
                if data:
                    # 包头：2字节序号 + 2字节长度
                    packet = struct.pack('!HH', seq, len(data)) + data
                    sock.sendall(packet)
                    seq = (seq + 1) % 65536  # 序号循环
            time.sleep(interval)  # 控制发送频率
        except Exception as e:
            print(f"串口到网络异常: {e}")
            break

def socket_to_serial(ser, sock):
    """网络到串口数据转发线程，并检测包头（序号和长度）"""
    buffer = b''
    last_seq = None
    while True:
        try:
            data = sock.recv(4096)
            print(data)
            if not data:
                print("服务器关闭了连接")
                break
            buffer += data
            # 按包头处理数据
            while len(buffer) >= 4:
                seq, length = struct.unpack('!HH', buffer[:4])
                if len(buffer) < 4 + length:
                    break  # 数据还不全，等待下次收齐
                payload = buffer[4:4+length]
                # 检查序号是否连续
                if last_seq is not None and seq != ((last_seq + 1) % 65536):
                    print(f"警告：序号异常！前序号: {last_seq} 当前序号: {seq}")
                last_seq = seq
                # 检查长度是否正确
                if len(payload) != length:
                    print(f"警告：长度异常！包头长度: {length} 实际长度: {len(payload)}")
                ser.write(payload)
                print(f"[收到] 序号: {seq} 长度: {length}")
                buffer = buffer[4+length:]  # 移除已处理数据
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
            time.sleep(10)  # 每分钟重连一次
        else:
            print("连接断开，1分钟后重试...")
            time.sleep(10)

if __name__ == '__main__':
    main()