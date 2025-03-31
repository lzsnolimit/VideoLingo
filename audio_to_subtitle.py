import os
import assemblyai as aai
import subprocess
import tempfile
import re
from pathlib import Path
from dotenv import load_dotenv

from subtitle_to_speech import process_subtitles

# 加载.env文件中的环境变量
load_dotenv()

def merge_subtitles(subtitle_file_path, format='srt'):
    """
    合并字幕，确保每个字幕块都以完整句子结尾（句号、问号、感叹号等）
    
    参数:
        subtitle_file_path (str): 字幕文件路径
        format (str): 字幕格式，'srt'或'vtt'
    
    返回:
        str: 处理后的字幕文件路径
    """
    # 读取原始字幕文件
    with open(subtitle_file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    if format.lower() == 'srt':
        # 使用正则表达式解析SRT格式
        # 匹配格式: 序号 + 时间码 + 文本
        pattern = r'(\d+)\s+(\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3})\s+([\s\S]*?)(?=\n\d+\s+\d{2}:\d{2}:\d{2},\d{3}|$)'
        subtitles = re.findall(pattern, content)
        
        # 初始化合并后的字幕列表
        merged_subtitles = []
        current_number = 1
        current_time = None
        current_text = ""
        
        for index, (number, time_code, text) in enumerate(subtitles):
            text = text.strip()
            
            # 如果当前无待处理文本，直接开始新段落
            if not current_text:
                current_time = time_code
                current_text = text
            # 如果当前文本已经以句号、问号或感叹号结尾，保存并开始新段落
            elif re.search(r'[.!?。！？]$', current_text):
                merged_subtitles.append((str(current_number), current_time, current_text))
                current_number += 1
                current_time = time_code
                current_text = text
            # 否则，将当前文本与下一段合并
            else:
                # 提取当前时间码的结束时间
                current_end_time = current_time.split(' --> ')[1]
                # 提取下一段时间码的结束时间
                next_end_time = time_code.split(' --> ')[1]
                # 更新时间码，保持开始时间不变，结束时间使用下一段的结束时间
                current_time = current_time.split(' --> ')[0] + ' --> ' + next_end_time
                # 合并文本，添加空格
                current_text += " " + text
        
        # 处理最后一段
        if current_text:
            merged_subtitles.append((str(current_number), current_time, current_text))
        
        # 重新组合成SRT格式
        merged_content = ""
        for number, time_code, text in merged_subtitles:
            merged_content += f"{number}\n{time_code}\n{text}\n\n"
        
    elif format.lower() == 'vtt':
        # 使用正则表达式解析VTT格式
        # 首先跳过VTT头部
        vtt_content = re.sub(r'^WEBVTT\s*\n', '', content)
        # 匹配格式: 时间码 + 文本
        pattern = r'(\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3})([\s\S]*?)(?=\n\d{2}:\d{2}:\d{2}\.\d{3}|$)'
        subtitles = re.findall(pattern, vtt_content)
        
        # 初始化合并后的字幕列表
        merged_subtitles = []
        current_time = None
        current_text = ""
        
        for index, (time_code, text) in enumerate(subtitles):
            text = text.strip()
            
            # 如果当前无待处理文本，直接开始新段落
            if not current_text:
                current_time = time_code
                current_text = text
            # 如果当前文本已经以句号、问号或感叹号结尾，保存并开始新段落
            elif re.search(r'[.!?。！？]$', current_text):
                merged_subtitles.append((current_time, current_text))
                current_time = time_code
                current_text = text
            # 否则，将当前文本与下一段合并
            else:
                # 提取当前时间码的结束时间
                current_end_time = current_time.split(' --> ')[1]
                # 提取下一段时间码的结束时间
                next_end_time = time_code.split(' --> ')[1]
                # 更新时间码，保持开始时间不变，结束时间使用下一段的结束时间
                current_time = current_time.split(' --> ')[0] + ' --> ' + next_end_time
                # 合并文本，添加空格
                current_text += " " + text
        
        # 处理最后一段
        if current_text:
            merged_subtitles.append((current_time, current_text))
        
        # 重新组合成VTT格式
        merged_content = "WEBVTT\n\n"
        for time_code, text in merged_subtitles:
            merged_content += f"{time_code}\n{text}\n\n"
    
    # 创建输出文件路径，格式为：原目录/merger_原文件名.扩展名
    subtitle_path = Path(subtitle_file_path)
    dir_path = subtitle_path.parent
    filename = subtitle_path.stem
    output_file_path = dir_path / f"merger_{filename}.{format}"
    
    # 写入合并后的字幕文件
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write(merged_content)
    
    print(f"合并后的字幕文件已保存至: {output_file_path}")
    return str(output_file_path)

def assembly_audio_to_subtitle(audio_path, api_key=None, format='srt'):
    """
    将音频文件转换为字幕文件
    
    参数:
        audio_path (str): 音频文件路径或URL
        api_key (str, optional): AssemblyAI API密钥。如未提供，将尝试从环境变量获取
        format (str, optional): 字幕格式，支持'srt'或'vtt'，默认为'srt'
    
    返回:
        str: 生成的字幕文件路径
    """
    # 设置API密钥
    if api_key:
        aai.settings.api_key = api_key
    elif os.environ.get('ASSEMBLYAI_API_KEY'):
        aai.settings.api_key = os.environ.get('ASSEMBLYAI_API_KEY')
    else:
        raise ValueError("必须提供API密钥或设置ASSEMBLYAI_API_KEY环境变量")
    
    # 创建转录器
    config = aai.TranscriptionConfig(speaker_labels=True)
    transcriber = aai.Transcriber(config=config)
    
    # 确保目标目录存在
    output_dir = Path("resources/transcripts")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 从音频路径获取文件名（不带扩展名）
    audio_file = Path(audio_path)
    base_filename = audio_file.stem
    
    # 转录音频文件
    print(f"开始转录音频文件: {audio_path}")
    transcript = transcriber.transcribe(audio_path)
    print("转录完成!")
    
    # 导出字幕
    subtitle_content = ""
    output_file_path = ""
    
    if format.lower() == 'srt':
        subtitle_content = transcript.export_subtitles_srt()
        output_file_path = output_dir / f"{base_filename}.srt"
    elif format.lower() == 'vtt':
        subtitle_content = transcript.export_subtitles_vtt()
        output_file_path = output_dir / f"{base_filename}.vtt"
    else:
        raise ValueError("字幕格式必须是'srt'或'vtt'")
    
    # 保存字幕文件
    with open(output_file_path, 'w', encoding='utf-8') as file:
        file.write(subtitle_content)
    
    print(f"字幕文件已保存至: {output_file_path}")
    
    # 合并字幕，确保每个字幕块以完整句子结尾
    merged_file_path = merge_subtitles(output_file_path, format)
    
    return merged_file_path
