#include <iostream>
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <cstring>

#include <string>
#include <map>
#include <regex>
#include <sstream>
#include "json.hpp"
using json = nlohmann::json;

// 判断buf中是否包含指定提示符
bool contains_prompt(const std::string& buf, const std::string& prompt) {
    return buf.find(prompt) != std::string::npos;
}
void clear_serial_remain(int fd) {
    char tempbuf[512];
    int empty_count = 0;
    while (empty_count < 2) { // 连续两次未读到数据即认定清空完成
        int n = read(fd, tempbuf, sizeof(tempbuf));
        if (n > 0) {
            empty_count = 0; // 只要读到数据，计数归零
        } else {
            ++empty_count;
        }
    }
}

// 处理mac-address整体输出，返回mac为键、接口为值的map
std::map<std::string, std::string> parse_mac_address_table(const std::string& text) {
    std::map<std::string, std::string> result;
    std::istringstream iss(text);
    std::string line;

    // 匹配类似 000b-0e0f-00ed ... GigabitEthernet1/0/2
    std::regex pattern(R"(^\s*([0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4})\s+\d+\s+\w+\s+([A-Za-z0-9/]+))");

    while (std::getline(iss, line)) {
        std::smatch match;
        if (std::regex_search(line, match, pattern)) {
            std::string mac = match[1];
            std::string iface = match[2];
            result[mac] = iface;
        }
    }
    return result;
}
int main() {
    const char* portname = "/dev/cot1"; // 串口名，根据实际情况调整
    int fd = open(portname, O_RDWR | O_NOCTTY);
    if (fd == -1) {
        perror("打开串口失败");
        return 1;
    }

    // 设置串口参数为原始模式，并设置读取超时
    struct termios tty;
    if (tcgetattr(fd, &tty) != 0) {
        perror("获取串口属性失败");
        close(fd);
        return 1;
    }
    cfmakeraw(&tty);
    cfsetospeed(&tty, B9600); // 波特率可根据实际设备调整
    cfsetispeed(&tty, B9600);

    tty.c_cc[VMIN] = 0;    // 最小读取字节数为0，只要有数据就返回
    tty.c_cc[VTIME] = 10;  // 读操作超时时间为1秒（单位为0.1秒）

    tcsetattr(fd, TCSANOW, &tty);

    const char* wakecmd = "\r\n";
    write(fd, wakecmd, strlen(wakecmd));
    tcdrain(fd);
    
    clear_serial_remain(fd);

    const char* lengthcmd = "screen-length disable\r\n";
    write(fd, lengthcmd, strlen(lengthcmd));
    tcdrain(fd);

    // 清空残留内容：一直读取，直到连续两次未读到数据认为清空完毕
    char tempbuf[512];
    int empty_count = 0; // 连续未读到数据次数
    while (empty_count < 2) { // 连续两次未读到数据即认定清空完成
        int n = read(fd, tempbuf, sizeof(tempbuf));
        if (n > 0) {
            empty_count = 0; // 读到数据则归零
        } else {
            ++empty_count;
        }
    }
    

    // 发送命令
    const char* cmd = "display device\r\n";
    write(fd, cmd, strlen(cmd));
    tcdrain(fd); // 等待数据发送完成

    // 读取内容，直到遇到提示符"<H3C>"或超时（20次未读到数据即退出）
    std::string buf;
    char rbuf[512];
    empty_count = 0; // 连续未读到数据次数
    while (empty_count < 10) { // 最多尝试20次，总计约2秒
        int n = read(fd, rbuf, sizeof(rbuf) - 1);
        if (n > 0) {
            rbuf[n] = '\0';
            buf += rbuf;
            // 检查是否出现提示符
            if (contains_prompt(buf, "<H3C>")) {
             std::cout<<"hit prompt"<<std::endl;
     		    break;
            }
            empty_count = 0; // 只要读到数据，计数归零
        } else {
            ++empty_count;
            usleep(100 * 1000); // 每次等待100ms
        }
    }

    // 输出完整响应内容
    std::cout << "交换机返回内容如下：" << std::endl;
    std::cout << buf << std::endl;

    // json j = parse_mac_address_table(buf);
    // std::string jsonStr = j.dump(4);
    // std::cout << "解析后的MAC地址表：" << std::endl;
    // std::cout << jsonStr << std::endl;

    close(fd);
    return 0;
}
