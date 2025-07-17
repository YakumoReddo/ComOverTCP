import serial
import socket
import threading
import time
import struct  # 用于解包包头

SERIAL_PORT = 'COM17'      # 修改成你的实际串口
BAUDRATE = 9600           # 和交换机一致
SERVER_PORT = 4000        # 监听的端口号

REFRESH_RATE = 30 # 刷新率（帧/秒）

clients = []              # 保存所有连接的客户端
clients_lock = threading.Lock()  # 用于同步访问clients列表

def serial_reader(ser):
    interval = 1.0/REFRESH_RATE
    print(f"[串口] 正在读取串口数据，刷新率: {REFRESH_RATE} FPS, 间隔: {interval:.3f} 秒")
    while True:
        try:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
                print(data)
                if data:
                    with clients_lock:
                        for client_sock in clients[:]:
                            
                            try:
                                client_sock.sendall(data)
                            except Exception as e:
                                print(f"[串口] 发送到客户端异常: {e}")
                                print(f"[串口] 移除掉线客户端")
                                clients.remove(client_sock)
                                try:
                                    client_sock.close()
                                except:
                                    pass
            time.sleep(interval)
        except Exception as e:
            print(f"[串口] 读取异常: {e}")
            time.sleep(1)

def socket_reader(ser, client_sock, addr):
    """处理来自客户端的数据，解析包头，仅写入payload部分到串口"""
    buffer = b''
    last_seq = None
    try:
        while True:
            data = client_sock.recv(4096)
            if not data:
                print(f"[网络] 客户端 {addr} 断开")
                break
            buffer += data
            # 处理每个包
            while len(buffer) >= 4:
                # 解析2字节序号+2字节长度
                seq, length = struct.unpack('!HH', buffer[:4])
                if len(buffer) < 4 + length:
                    break  # 数据还没收齐，等待下次
                payload = buffer[4:4+length]
                # 检查序号是否连续
                if last_seq is not None and seq != ((last_seq + 1) % 65536):
                    print(f"警告：序号异常！前序号: {last_seq} 当前序号: {seq}")
                last_seq = seq
                # 检查长度是否正确
                if len(payload) != length:
                    print(f"警告：长度异常！包头长度: {length} 实际长度: {len(payload)}")
                # 只将payload部分写入串口
                ser.write(payload)
                print("<<",payload,end="")
                print(f"[收到] 序号: {seq} 长度: {length}")
                buffer = buffer[4+length:]  # 移除已处理部分
    except Exception as e:
        print(f"[网络] 客户端 {addr} 读取异常: {e}")
    finally:
        with clients_lock:
            if client_sock in clients:
                clients.remove(client_sock)
                print(f"[网络] 客户端 {addr} 已移除")
        try:
            client_sock.close()
        except:
            pass

def client_handler(ser, client_sock, addr):
    socket_reader(ser, client_sock, addr)

def main():
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', SERVER_PORT))
    server.listen(5)
    server.settimeout(1.0)  # 设置 accept 超时为 1 秒
    print(f'等待客户端连接，监听端口 {SERVER_PORT}...')

    t_serial = threading.Thread(target=serial_reader, args=(ser,), daemon=True)
    t_serial.start()

    try:
        while True:
            try:
                client_sock, addr = server.accept()
            except socket.timeout:
                continue  # 超时则继续循环，可响应 KeyboardInterrupt
            print(f'客户端已连接: {addr}')
            with clients_lock:
                clients.append(client_sock)
            t = threading.Thread(target=client_handler, args=(ser, client_sock, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("服务器已手动退出")
    finally:
        ser.close()
        with clients_lock:
            for c in clients:
                try:
                    c.close()
                except:
                    pass
        server.close()

if __name__ == '__main__':
    main()