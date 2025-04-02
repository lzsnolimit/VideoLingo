import os
import subprocess
import time
import re
import sys
from pathlib import Path

import audio_to_subtitle

def extract_video_id(url):
    """从YouTube URL中提取视频ID"""
    # 尝试匹配常见的YouTube URL格式
    pattern = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

def download_youtube(url, content_type="video", quality="best", audio_format="mp3", audio_quality="0", show_progress=True, threads=8):
    """
    使用yt-dlp下载YouTube视频或音频到指定目录，使用视频ID或时间戳作为文件名
    
    参数:
        url (str): YouTube视频URL
        content_type (str): 内容类型，'video'或'audio'
        quality (str): 视频质量，默认为'best'，可选值如:
                      - 'best': 最佳视频和音频质量
                      - '1080p': 1080p视频
                      - '720p': 720p视频
        audio_format (str): 音频格式，默认'mp3'，可选'm4a'、'wav'、'opus'等
        audio_quality (str): 音频质量，0(最好)到9(最差)，默认为0
        show_progress (bool): 是否显示下载进度，默认为True
        threads (int): 并行下载的线程数量，默认为8
    
    返回:
        str: 成功时返回下载文件的相对路径，失败时返回错误信息
    """
    
    # 尝试提取视频ID，如果失败则使用时间戳
    video_id = extract_video_id(url)
    if not video_id:
        video_id = str(int(time.time()))
    
    # 构建命令
    command = ["yt-dlp"]
    
    # 添加多线程下载参数
    if threads > 1:
        command.extend(["--concurrent-fragments", str(threads)])
    
    if content_type == "video":
        # 构建视频格式参数
        if quality == "best":
            format_arg = "bestvideo+bestaudio/best"
        elif quality == "1080p":
            format_arg = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        elif quality == "720p":
            format_arg = "bestvideo[height<=720]+bestaudio/best[height<=720]"
        else:
            format_arg = quality
        
        command.extend([
            "-f", format_arg,
            "--merge-output-format", "mp4"
        ])
        output_dir = "resources/videos"
        file_path = f"{output_dir}/{video_id}.mp4"
        output_template = file_path
    
    else:  # 音频下载
        command.extend([
            "-x",  # 提取音频
            "--audio-format", audio_format,
            "--audio-quality", str(audio_quality)  # 确保 audio_quality 被转换为字符串
        ])
        output_dir = "resources/audios"
        file_path = f"{output_dir}/{video_id}.{audio_format}"
        output_template = file_path
    
    # 确保输出目录存在
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 添加输出模板
    command.extend(["-o", output_template])
    
    # 添加URL
    command.append(url)
    
    try:
        if show_progress:
            # 使用 Popen 实时获取输出以显示进度
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # 实时读取输出并显示进度
            for line in process.stdout:
                line = line.strip()
                # 过滤并显示下载进度信息
                if '[download]' in line and '%' in line:
                    print(f"\r{line}", end='', flush=True)
                # 显示多线程下载信息
                elif 'fragment' in line.lower() and '%' in line:
                    print(f"\r{line}", end='', flush=True)
                
            # 等待进程完成
            process.wait()
            print()  # 换行，保持输出整洁
            
            # 检查返回码
            if process.returncode != 0:
                return f"下载失败，返回码: {process.returncode}"
        else:
            # 使用原来的方式执行命令
            result = subprocess.run(
                command, 
                check=True,
                capture_output=True,
                text=True
            )
        
        # 检查文件是否存在
        if os.path.exists(file_path):
            return file_path
        
        # 如果找不到预期的文件，尝试从输出中提取
        print("找不到文件: {}".format(file_path))
        
        if show_progress:
            return file_path
        else:
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines:
                if "Destination" in line and ":" in line:
                    return line.split(":", 1)[1].strip()
                elif "[Merger] Merging formats into" in line:
                    return line.replace("[Merger] Merging formats into ", "").replace('"', '').strip()
        
        # 如果仍然找不到，返回可能的路径
        return file_path
    
    except subprocess.CalledProcessError as e:
        return f"下载失败: {e.stderr}"
    
    except Exception as e:
        return f"发生错误: {str(e)}"

    

    