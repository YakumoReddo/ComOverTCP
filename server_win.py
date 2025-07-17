import serial
import socket
import threading
import time

SERIAL_PORT = 'COM17'      # 修改成你的实际串口
BAUDRATE = 9600           # 和交换机一致
SERVER_PORT = 4000        # 监听的端口号

clients = []              # 保存所有连接的客户端
clients_lock = threading.Lock()  # 用于同步访问clients列表

def serial_reader(ser):
    """不断高频率地读串口并广播到所有客户端"""
    while True:
        try:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
                if data:
                    print(data, end="")  # 打印串口收到的数据
                    # 广播到所有客户端
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
                    time.sleep(0.001)
            else:
                time.sleep(0.001)
        except Exception as e:
            print(f"[串口] 读取异常: {e}")
            time.sleep(1)

def socket_reader(ser, client_sock, addr):
    """不断接收网络数据并写入串口"""
    try:
        while True:
            data = client_sock.recv(4096)  # 一次收大块
            if not data:
                print(f"[网络] 客户端 {addr} 断开")
                break
            ser.write(data)
            print("<<", data, end="")
    except Exception as e:
        print(f"[网络] 客户端 {addr} 读取异常: {e}")
    finally:
        # 客户端断开或异常时，从列表移除
        with clients_lock:
            if client_sock in clients:
                clients.remove(client_sock)
                print(f"[网络] 客户端 {addr} 已移除")
        try:
            client_sock.close()
        except:
            pass

def client_handler(ser, client_sock, addr):
    """启动单独线程处理每个客户端的写入串口任务"""
    socket_reader(ser, client_sock, addr)

def main():
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', SERVER_PORT))
    server.listen(5)
    print(f'等待客户端连接，监听端口 {SERVER_PORT}...')

    # 启动串口读取广播线程
    t_serial = threading.Thread(target=serial_reader, args=(ser,), daemon=True)
    t_serial.start()

    try:
        while True:
            client_sock, addr = server.accept()
            print(f'客户端已连接: {addr}')
            with clients_lock:
                clients.append(client_sock)
            # 启动每个客户端的socket读取线程
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