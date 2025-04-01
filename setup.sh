#!/bin/bash

# 激活虚拟环境
source audio_env/bin/activate

# 安装基础依赖
pip install -r requirements-base.txt

# 提示用户选择需要安装的功能
echo "请选择需要安装的功能(多选请用空格分隔):"
echo "1. Spleeter (音频分离)"
echo "2. Fish Audio SDK"
echo "3. AssemblyAI (语音识别)"
echo "输入功能编号(例如: 1 2 3): "
read choices

# 根据用户选择安装相应依赖
for choice in $choices; do
  case $choice in
    1)
      echo "正在安装 Spleeter..."
      pip install -r requirements-spleeter.txt
      ;;
    2)
      echo "正在安装 Fish Audio SDK..."
      pip install -r requirements-fish.txt
      ;;
    3)
      echo "正在安装 AssemblyAI..."
      pip install -r requirements-assemblyai.txt
      ;;
    *)
      echo "无效选择: $choice"
      ;;
  esac
done

echo "安装完成!" 