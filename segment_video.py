import re
import os
import json
import subprocess
from typing import List, Tuple, Dict
from datetime import datetime, timedelta
from langchain.prompts import PromptTemplate
from langchain_deepseek import ChatDeepSeek
from langchain_core.output_parsers import StrOutputParser
import json
from dateutil import parser


def parse_srt(content: str) -> List[Tuple[str, str, str]]:
    """
    解析SRT文件内容
    
    Args:
        content: SRT文件内容
        
    Returns:
        解析后的字幕块列表，每个元素为(序号, 时间戳, 文本)的元组
    """
    # 使用正则表达式匹配SRT文件的各个部分
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\n((?:.+\n)+?)(?:\n|$)'
    matches = re.findall(pattern, content, re.MULTILINE)
    
    subtitle_blocks = []
    for match in matches:
        idx = match[0]
        timestamp = match[1]
        text = match[2].strip()
        subtitle_blocks.append((idx, timestamp, text))
    
    return subtitle_blocks


def timestamp_to_seconds(timestamp: str) -> float:
    """
    将SRT时间戳转换为秒数
    
    Args:
        timestamp: SRT格式的时间戳 (HH:MM:SS,mmm)
        
    Returns:
        时间戳对应的秒数
    """
    # 解析时间戳格式
    time_parts = timestamp.split(':')
    seconds_parts = time_parts[2].split(',')
    
    hours = int(time_parts[0])
    minutes = int(time_parts[1])
    seconds = int(seconds_parts[0])
    milliseconds = int(seconds_parts[1])
    
    total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
    return total_seconds


def get_subtitle_time_range(subtitle_block: Tuple[str, str, str]) -> Tuple[float, float]:
    """
    获取字幕块的开始和结束时间
    
    Args:
        subtitle_block: 字幕块元组 (序号, 时间戳, 文本)
        
    Returns:
        (开始时间(秒), 结束时间(秒))的元组
    """
    _, timestamp, _ = subtitle_block
    start_time, end_time = timestamp.split(' --> ')
    
    start_seconds = timestamp_to_seconds(start_time)
    end_seconds = timestamp_to_seconds(end_time)
    
    return start_seconds, end_seconds


def seconds_to_timestamp(seconds: float) -> str:
    """
    将秒数转换为SRT时间戳格式
    
    Args:
        seconds: 秒数
        
    Returns:
        SRT格式的时间戳 (HH:MM:SS,mmm)
    """
    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    seconds %= 60
    whole_seconds = int(seconds)
    milliseconds = int((seconds - whole_seconds) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def get_video_duration(video_file: str) -> float:
    """
    使用ffprobe获取视频文件的精确时长
    
    Args:
        video_file: 视频文件路径
        
    Returns:
        视频时长（秒）
    """
    try:
        cmd = [
            'ffprobe', 
            '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'json', 
            video_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
    except Exception as e:
        print(f"获取视频时长时出错: {str(e)}")
        return None


def analyze_subtitles_for_segmentation(srt_file: str, video_file: str, min_duration: int = 60, max_duration: int = 180) -> List[Dict]:
    """
    分析字幕文件，使用AI确定合适的视频分段点
    
    Args:
        srt_file: SRT字幕文件路径
        video_file: 视频文件路径
        min_duration: 最小片段时长（秒），默认60秒
        max_duration: 最大片段时长（秒），默认180秒（3分钟）
        
    Returns:
        包含每个片段信息的字典列表，每个字典包含开始时间、结束时间、时长和内容摘要
    """
    print(f"开始分析字幕文件以进行分段: {srt_file}")
    
    # 读取SRT文件
    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析SRT文件
    subtitle_blocks = parse_srt(content)
    print(f"共解析出 {len(subtitle_blocks)} 个字幕块")
    
    # 获取视频总时长
    video_duration = get_video_duration(video_file)
    if video_duration is None:
        # 如果无法获取视频时长，则回退到使用字幕末尾时间的方法
        _, last_timestamp, _ = subtitle_blocks[-1]
        _, video_end_time = last_timestamp.split(' --> ')
        video_duration = timestamp_to_seconds(video_end_time)
        print(f"警告：无法获取准确视频时长，使用字幕结束时间作为替代: {video_duration:.2f} 秒")
    else:
        print(f"视频总时长: {video_duration:.2f} 秒 ({video_duration/60:.2f} 分钟)")
    
    # 收集所有文本及其时间戳
    subtitle_data = []
    for block in subtitle_blocks:
        idx, timestamp, text = block
        start_time, end_time = timestamp.split(' --> ')
        start_seconds = timestamp_to_seconds(start_time)
        end_seconds = timestamp_to_seconds(end_time)
        
        subtitle_data.append({
            "id": idx,
            "start_time": start_seconds,
            "end_time": end_seconds,
            "text": text
        })
    
    # 设置AI分析提示模板
    template = """
    你是一位专业的视频编辑和内容分析专家，需要将一个长视频切分成多个短视频片段。你的首要任务是深入理解字幕内容的语义和主题变化，找出最佳分段点。
    
    分析步骤：
    1. 仔细阅读所有字幕内容，理解整体故事情节和主题变化
    2. 识别内容中的关键转折点、主题变化、场景切换或情感变化
    3. 在这些自然切换点处进行分段，确保每个片段都有完整、连贯的内容
    4. 调整分段时间，使其符合时长要求
    
    分段规则（按重要性排序）：
    1. 内容连贯性优先：每个片段必须包含语义完整、主题一致的内容
    2. 在自然的语义转折点切分：如主题变化、场景转换、问题解答完成等
    3. 尊重句子完整性：绝不在句子中间切分
    4. 时长范围：每个片段长度应在 {min_duration} 秒到 {max_duration} 秒之间
    5. 切分点选择：宁可选择意义完整的较长片段，也不要生成内容破碎的短片段
    
    以下是字幕内容及其时间信息（JSON格式）：
    
    {subtitle_data}
    
    请分析这些字幕内容，找出最符合内容语义的最佳视频切分点。
    
    返回JSON数组，每个元素为一个字典，包含以下字段：
    - start_time: 片段开始时间（秒），精确到小数点后3位（毫秒级别）
    - end_time: 片段结束时间（秒），精确到小数点后3位（毫秒级别）
    - duration: 片段时长（秒），精确到小数点后3位
    - summary: 该片段的内容简短摘要（不超过30个字）
    - reason: 为什么在此处分段的简短解释（如：主题转换、场景变化等）
    
    只返回有效的JSON数组，不要包含任何其他解释或文本。
    """
    
    prompt = PromptTemplate(
        input_variables=["subtitle_data", "min_duration", "max_duration"],
        template=template
    )
    
    # 初始化LangChain模型
    print("初始化AI分析模型...")
    llm = ChatDeepSeek(
        model="deepseek-reasoner",
        temperature=0.1,  # 降低温度以获得更一致和确定性的输出
        max_tokens=None,
        timeout=None,
        max_retries=3,
        api_key=os.getenv("DEEPSEEK_API_KEY")
    )
    
    # 创建处理链
    chain = prompt | llm | StrOutputParser()
    
    # 调用AI模型进行分析
    print("使用AI分析适合的视频分段点...")
    try:
        result = chain.invoke({
            "subtitle_data": json.dumps(subtitle_data, ensure_ascii=False, indent=2),
            "min_duration": min_duration,
            "max_duration": max_duration
        })
        
        # 解析JSON结果
        segments = json.loads(result)
        
        # 验证生成的片段
        validated_segments = []
        for i, segment in enumerate(segments):
            # 确保每个片段都有必需的字段
            required_fields = ["start_time", "end_time", "duration", "summary"]
            if all(k in segment for k in required_fields):
                # 验证时长是否在允许范围内
                duration = segment["end_time"] - segment["start_time"]
                if min_duration <= duration <= max_duration:
                    # 添加序号和格式化的时间戳
                    segment["id"] = i + 1
                    segment["start_timestamp"] = seconds_to_timestamp(segment["start_time"])
                    segment["end_timestamp"] = seconds_to_timestamp(segment["end_time"])
                    
                    # 如果没有reason字段，添加一个默认值
                    if "reason" not in segment:
                        segment["reason"] = "内容主题完整"
                        
                    validated_segments.append(segment)
                else:
                    print(f"警告：片段 {i+1} 时长 ({duration:.2f}秒) 不在允许范围内")
            else:
                missing = [f for f in required_fields if f not in segment]
                print(f"警告：片段 {i+1} 缺少必需字段：{', '.join(missing)}")
        
        print(f"AI分析完成，生成了 {len(validated_segments)} 个有效片段")
        return validated_segments
    
    except Exception as e:
        print(f"AI分析过程中出现错误: {str(e)}")
        # 如果AI分析失败，使用简单的时间等分方法作为后备
        return create_fallback_segments(subtitle_data, video_duration, min_duration, max_duration)


def create_fallback_segments(subtitle_data: List[Dict], video_duration: float, 
                             min_duration: int = 60, max_duration: int = 180) -> List[Dict]:
    """
    当AI分析失败时，创建基于语义和时间的备用分段方案
    
    Args:
        subtitle_data: 字幕数据
        video_duration: 视频总时长（秒）
        min_duration: 最小片段时长（秒）
        max_duration: 最大片段时长（秒）
        
    Returns:
        包含每个片段信息的字典列表
    """
    print("使用智能备用方法创建片段...")
    
    # 如果字幕数据为空，则回退到简单的时间等分
    if not subtitle_data:
        print("警告：字幕数据为空，使用纯时间等分")
        return create_simple_time_segments(video_duration, min_duration, max_duration)
    
    segments = []
    current_start = 0
    current_duration = 0
    segment_subtitles = []
    
    # 基于句号、问号等标点符号识别自然段落结尾
    sentence_end_patterns = [
        '。', '？', '！',  # 中文
        '.', '?', '!',    # 英文
        '\n\n'            # 空行（可能表示段落转换）
    ]
    
    # 初始化当前片段的起始位置
    current_segment_start = subtitle_data[0]["start_time"]
    current_segment_subtitles = []
    
    for i, subtitle in enumerate(subtitle_data):
        # 添加当前字幕到当前片段的字幕列表
        current_segment_subtitles.append(subtitle)
        
        # 计算当前积累的时长
        if i > 0:
            current_duration = subtitle["end_time"] - current_segment_start
        
        # 检查是否达到了最小时长且可能是语义自然结束点
        is_min_duration_reached = current_duration >= min_duration
        is_max_duration_exceeded = current_duration >= max_duration
        
        # 检查是否是自然句子结束点
        is_sentence_end = False
        if subtitle["text"]:
            for pattern in sentence_end_patterns:
                if pattern in subtitle["text"]:
                    is_sentence_end = True
                    break
        
        # 决定是否在这里分段
        should_segment = False
        reason = ""
        
        # 如果超过最大时长，强制分段
        if is_max_duration_exceeded:
            should_segment = True
            reason = "达到最大时长限制"
        # 如果达到最小时长且是句子结束，在自然断点分段
        elif is_min_duration_reached and is_sentence_end:
            should_segment = True
            reason = "在自然语句结束处分段"
        # 如果是最后一个字幕，必须分段
        elif i == len(subtitle_data) - 1:
            should_segment = True
            reason = "视频结束"
        
        # 如果应该在这里分段
        if should_segment:
            # 创建当前片段
            segment_start_time = current_segment_start
            segment_end_time = subtitle["end_time"]
            duration = segment_end_time - segment_start_time
            
            # 创建摘要（使用第一个字幕内容的开头）
            if current_segment_subtitles:
                first_subtitle = current_segment_subtitles[0]["text"]
                summary = first_subtitle[:30] + ("..." if len(first_subtitle) > 30 else "")
            else:
                summary = f"片段 {len(segments) + 1}"
            
            segments.append({
                "id": len(segments) + 1,
                "start_time": round(segment_start_time, 3),
                "end_time": round(segment_end_time, 3),
                "duration": round(duration, 3),
                "start_timestamp": seconds_to_timestamp(segment_start_time),
                "end_timestamp": seconds_to_timestamp(segment_end_time),
                "summary": summary,
                "reason": reason
            })
            
            # 重置当前片段
            if i < len(subtitle_data) - 1:
                current_segment_start = subtitle_data[i + 1]["start_time"]
                current_segment_subtitles = []
                current_duration = 0
    
    # 如果没有生成任何片段（极端情况），回退到简单的时间等分
    if not segments:
        print("警告：备用方法未能生成有效片段，回退到纯时间等分")
        return create_simple_time_segments(video_duration, min_duration, max_duration)
    
    print(f"创建了 {len(segments)} 个基于语义断点的备用片段")
    return segments


def create_simple_time_segments(video_duration: float, min_duration: int = 15, max_duration: int = 180) -> List[Dict]:
    """
    创建简单的基于时间等分的片段
    
    Args:
        video_duration: 视频总时长（秒）
        min_duration: 最小片段时长（秒）
        max_duration: 最大片段时长（秒）
        
    Returns:
        包含每个片段信息的字典列表
    """
    print("使用纯时间等分方法创建片段...")
    
    # 计算片段数量，尽量接近最大长度但不超过
    num_segments = max(1, int(video_duration // max_duration))
    segment_duration = video_duration / num_segments
    
    segments = []
    for i in range(num_segments):
        # 确保时间精确到毫秒
        start_time = round(i * segment_duration, 3)  # 保留3位小数（毫秒级）
        end_time = round(min((i + 1) * segment_duration, video_duration), 3)
        duration = round(end_time - start_time, 3)
        
        segments.append({
            "id": i + 1,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "start_timestamp": seconds_to_timestamp(start_time),
            "end_timestamp": seconds_to_timestamp(end_time),
            "summary": f"片段 {i+1}",
            "reason": "时间等分"
        })
    
    print(f"创建了 {len(segments)} 个基于纯时间等分的片段")
    return segments


def generate_ffmpeg_commands(video_file: str, segments: List[Dict], output_dir: str = "segments") -> List[str]:
    """
    为每个片段生成ffmpeg命令
    
    Args:
        video_file: 输入视频文件路径
        segments: 片段信息列表
        output_dir: 输出目录
        
    Returns:
        ffmpeg命令列表
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 从原始文件路径中提取文件名和扩展名
    base_name = os.path.basename(video_file)
    file_name, file_ext = os.path.splitext(base_name)
    
    # 如果没有扩展名，默认使用.mp4
    if not file_ext:
        file_ext = ".mp4"
    
    commands = []
    for i, segment in enumerate(segments):
        # 使用原始文件名_{序号}.{原扩展名}格式
        output_file = os.path.join(output_dir, f"{file_name}_{segment['id']:03d}{file_ext}")
        
        # 使用精确的时间戳格式而不是秒数
        start_timestamp = segment["start_timestamp"].replace(',', '.')  # ffmpeg使用点而不是逗号作为毫秒分隔符
        
        # 生成ffmpeg命令
        # 对于最后一个片段，不指定结束时间，让其默认截取到视频末尾
        if i == len(segments) - 1:
            cmd = (f'ffmpeg -i "{video_file}" -ss {start_timestamp} '
                   f'-c:v libx264 -c:a aac -strict experimental "{output_file}"')
        else:
            end_timestamp = segment["end_timestamp"].replace(',', '.')
            cmd = (f'ffmpeg -i "{video_file}" -ss {start_timestamp} -to {end_timestamp} '
                   f'-c:v libx264 -c:a aac -strict experimental "{output_file}"')
        
        commands.append(cmd)
    
    return commands


def segment_video(srt_file: str, video_file: str, output_dir: str = "segments", 
                  min_duration: int = 15, max_duration: int = 180) -> Dict:
    """
    根据字幕文件分析，将视频切割成多个短片段
    
    Args:
        srt_file: SRT字幕文件路径
        video_file: 视频文件路径
        output_dir: 输出目录
        min_duration: 最小片段时长（秒），默认15秒
        max_duration: 最大片段时长（秒），默认180秒（3分钟）
        
    Returns:
        包含分段信息的字典
    """
    print(f"开始视频分段处理...")
    print(f"字幕文件: {srt_file}")
    print(f"视频文件: {video_file}")
    print(f"输出目录: {output_dir}")
    print(f"分段时长要求: {min_duration}秒 - {max_duration}秒")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 分析字幕并获取分段信息
    segments = analyze_subtitles_for_segmentation(srt_file, video_file, min_duration, max_duration)
    
    # 生成ffmpeg命令
    ffmpeg_commands = generate_ffmpeg_commands(video_file, segments, output_dir)
    
    # 创建一个包含分段和命令的完整结果字典
    result = {
        "video_file": video_file,
        "srt_file": srt_file,
        "segment_count": len(segments),
        "segments": segments,
        "ffmpeg_commands": ffmpeg_commands,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 保存分段信息到JSON文件
    segments_json_file = os.path.join(output_dir, "segments_info.json")
    with open(segments_json_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 同时生成一个易于阅读的文本报告
    report_file = os.path.join(output_dir, "segments_report.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"视频分段报告\n")
        f.write(f"='='='='='='='='='='='='='='='='='='='='=\n\n")
        f.write(f"视频文件: {video_file}\n")
        f.write(f"字幕文件: {srt_file}\n")
        f.write(f"分段时长要求: {min_duration}秒 - {max_duration}秒\n")
        f.write(f"分段总数: {len(segments)}\n\n")
        f.write(f"分段详情:\n")
        f.write(f"-----------------------------\n\n")
        
        for seg in segments:
            f.write(f"片段 {seg['id']}:\n")
            f.write(f"  时间范围: {seg['start_timestamp']} - {seg['end_timestamp']}\n")
            f.write(f"  时长: {seg['duration']:.2f} 秒\n")
            f.write(f"  内容摘要: {seg['summary']}\n")
            if 'reason' in seg:
                f.write(f"  分段原因: {seg['reason']}\n")
            f.write(f"\n")
            
            # 为每个片段生成单独的命令文件，方便用户单独执行
            cmd_file = os.path.join(output_dir, f"cmd_segment_{seg['id']:03d}.sh")
            with open(cmd_file, 'w', encoding='utf-8') as cmd_f:
                cmd_f.write("#!/bin/sh\n")
                cmd_f.write(ffmpeg_commands[seg['id']-1])
            # 设置可执行权限
            os.chmod(cmd_file, 0o755)
            # 为每个片段生成单独的命令文件，方便用户单独执行
            # 从原始文件路径中提取文件名
            base_name = os.path.basename(video_file)
            file_name, _ = os.path.splitext(base_name)
            
            # 命令文件名也使用原始文件名作为前缀
            cmd_file = os.path.join(output_dir, f"cmd_{file_name}_{seg['id']:03d}.sh")
            with open(cmd_file, 'w', encoding='utf-8') as cmd_f:
                cmd_f.write("#!/bin/sh\n")
                cmd_f.write(ffmpeg_commands[seg['id']-1])
            # 设置可执行权限
            os.chmod(cmd_file, 0o755)
    
    print(f"分段分析完成，共生成 {len(segments)} 个片段")
    print(f"详细报告已保存至: {report_file}")
    print(f"分段信息已保存至: {segments_json_file}")
    print(f"每个片段的单独命令脚本已保存在 {output_dir} 目录中")
    
    # 打印简短的分段概览
    print("\n片段概览:")
    for seg in segments:
        duration_str = f"{seg['duration']:.1f}秒"
        print(f"  片段 {seg['id']:03d}: {duration_str:>7} | {seg['summary']}")
    
    return result


def execute_ffmpeg_commands(commands: List[str], max_parallel: int = 2) -> None:
    """
    执行ffmpeg命令列表（可选功能）
    
    Args:
        commands: ffmpeg命令列表
        max_parallel: 最大并行执行数量
    """
    import subprocess
    import concurrent.futures
    
    print(f"开始执行视频切割，最大并行数: {max_parallel}")
    
    def run_command(cmd):
        print(f"执行命令: {cmd}")
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        return process.returncode, cmd, stdout, stderr
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures = [executor.submit(run_command, cmd) for cmd in commands]
        
        for future in concurrent.futures.as_completed(futures):
            returncode, cmd, stdout, stderr = future.result()
            if returncode == 0:
                print(f"命令执行成功: {cmd}")
            else:
                print(f"命令执行失败 (返回码 {returncode}): {cmd}")
                print(f"错误: {stderr.decode('utf-8', errors='replace')}")
    
    print("所有视频切割命令执行完毕")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="基于字幕分析的视频切割工具")
    parser.add_argument("srt_file", help="SRT字幕文件路径")
    parser.add_argument("video_file", help="视频文件路径")
    parser.add_argument("--output_dir", default="segments", help="输出目录")
    parser.add_argument("--min_duration", type=int, default=240, help="最小片段时长（秒）")
    parser.add_argument("--max_duration", type=int, default=480, help="最大片段时长（秒）")
    parser.add_argument("--no-execute", dest="execute", action="store_false", help="不执行ffmpeg命令，只生成命令列表")
    parser.add_argument("--max_parallel", type=int, default=10, help="最大并行执行数量")
    
    parser.set_defaults(execute=True)
    
    args = parser.parse_args()
    
    # 进行视频分段分析
    result = segment_video(
        args.srt_file, 
        args.video_file, 
        args.output_dir,
        args.min_duration,
        args.max_duration
    )
    
    # 如果指定了execute参数，则执行ffmpeg命令
    if args.execute:
        execute_ffmpeg_commands(result["ffmpeg_commands"], args.max_parallel)
    else:
        print("\n要执行视频切割，可以手动运行以下命令:")
        for cmd in result["ffmpeg_commands"]:
            print(cmd) 