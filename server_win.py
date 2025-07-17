import serial
import socket
import threading
import time

SERIAL_PORT = 'COM17'      # 修改成你的实际串口
BAUDRATE = 9600           # 和交换机一致
SERVER_PORT = 4000        # 监听的端口号

REFRESH_RATE = 30 # 刷新率（帧/秒）

clients = []              # 保存所有连接的客户端
clients_lock = threading.Lock()  # 用于同步访问clients列表

def serial_reader(ser):
    interval = 1.0/REFRESH_RATE
    while True:
        try:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
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
    try:
        while True:
            data = client_sock.recv(4096)
            if not data:
                print(f"[网络] 客户端 {addr} 断开")
                break
            ser.write(data)
            print("<<", data, end="\n")
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