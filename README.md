# K230 RTOS Only SDK 开发指南

## 概述

K230 RTOS Only SDK 是基于K230芯片和RT-Smart实时操作系统的软件开发套件，提供完整的开发环境和工具链，帮助开发者快速构建嵌入式应用。CanMV_K230项目是本SDK的典型应用案例，通过MicroPython框架简化了硬件评估和原型开发流程。

## 获取镜像

### 每日构建版本
- **下载地址**: [Daily Build镜像](https://kendryte-download.canaan-creative.com/developer/releases/canmv_k230_micropython/daily_build/)
- **特点**:
  - 自动构建的开发分支最新版本
  - 适合测试和尝鲜使用
  - 仅保留最新构建版本

### 稳定发布版本
- **获取方式**:
  1. 访问[嘉楠开发者社区资源中心](https://developer.canaan-creative.com/resource)
  2. 在`K230/Images`分类中查找
  3. 下载文件名包含`RTSmart`的镜像文件（格式示例：`RtSmart_*.img.gz`）

> **注意**: 下载的镜像为gzip压缩格式，使用前需先解压

## 快速入门

### 镜像编译指南

我们提供两种编译方式供选择：

**方法一：使用Docker环境（推荐）**
- 优势：环境隔离，依赖完整
- 参考文档：[BUILD编译指南](BUILD.md)

**方法二：本地环境编译**
- 优势：编译速度更快
- 系统要求：Ubuntu 20.04/22.04 LTS

详细步骤请参考：
[K230 RTOS 自定义固件编译教程](https://www.kendryte.com/k230_rtos/zh/main/userguide/how_to_build.html)

### 镜像烧录方法

**Linux系统**:
```bash
dd if=镜像文件 of=/dev/sdX bs=1M status=progress
```

**Windows系统**:
- 推荐使用专业烧录工具
- 操作指南：[K230 CanMV 固件烧录教程](https://www.kendryte.com/k230_rtos/zh/main/userguide/how_to_flash.html)

## 贡献与支持

### 参与贡献
我们欢迎各种形式的贡献，包括但不限于：
- 问题反馈
- 文档改进
- 代码提交

请阅读[贡献指南](CONTRIBUTING.md)了解详细流程。

### 技术支持
**北京嘉楠捷思信息技术有限公司**  
官网：[www.canaan-creative.com](https://www.canaan-creative.com/)  
技术支持邮箱：[support@canaan-creative.com](mailto:support@canaan-creative.com)  
商务合作：[salesAI@canaan-creative.com](mailto:salesAI@canaan-creative.com)

---

> **提示**：建议开发者定期关注[官方GitHub仓库](https://github.com/kendryte/canmv_k230)获取最新更新和安全补丁。
