import re
import os
import json
from typing import List, Dict, Tuple
from langchain.prompts import PromptTemplate
from langchain_deepseek import ChatDeepSeek
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI


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


def detect_ads_in_subtitles(srt_file: str) -> List[Dict]:
    """
    分析字幕文件，使用AI识别其中的广告部分
    
    Args:
        srt_file: SRT字幕文件路径
        
    Returns:
        包含每个广告片段信息的字典列表，每个字典包含开始时间、结束时间和理由
    """
    print(f"开始分析字幕文件以查找广告: {srt_file}")
    
    # 读取SRT文件
    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析SRT文件
    subtitle_blocks = parse_srt(content)
    print(f"共解析出 {len(subtitle_blocks)} 个字幕块")
    
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
    你是一位专业的视频内容分析专家，需要分析一段视频的字幕，找出其中的广告部分。
    
    分析步骤：
    1. 仔细阅读所有字幕内容，理解整体内容
    2. 识别可能是广告的部分，包括产品推广、赞助商信息、自我推广等
    3. 判断每段广告的开始和结束时间点
    
    广告特征（任何一条都可能表明这是广告）：
    1. 与主要内容无关的产品/服务介绍
    2. 对赞助商的明确提及
    3. 打折码、优惠券的提及
    4. 鼓励订阅、点赞、关注等号召性用语
    5. 与内容主题突然转变的部分
    6. 介绍自己其他内容/频道/社交媒体的部分
    
    以下是字幕内容及其时间信息（JSON格式）：
    
    {subtitle_data}
    
    请分析这些字幕内容，找出所有可能的广告部分。
    
    返回JSON数组，每个元素为一个字典，包含以下字段：
    - start_time: 广告开始时间（秒），精确到小数点后3位
    - end_time: 广告结束时间（秒），精确到小数点后3位
    - duration: 广告时长（秒），精确到小数点后3位
    - reason: 判断为广告的理由，简短说明
    
    如果没有识别出广告部分，则返回空数组。
    只返回有效的JSON数组，不要包含任何其他解释或文本。
    """
    
    prompt = PromptTemplate(
        input_variables=["subtitle_data"],
        template=template
    )
    
    # 初始化LangChain模型
    print("初始化AI分析模型...")
    # llm = ChatDeepSeek(
    #     model="deepseek-reasoner",
    #     temperature=0.5,  # 降低温度以获得更一致和确定性的输出
    #     max_tokens=None,
    #     timeout=None,
    #     max_retries=3,
    #     api_key=os.getenv("DEEPSEEK_API_KEY")
    # )
    llm=ChatOpenAI(
        model="gpt-4.1",
        temperature=0.1,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    )
    
    # 创建处理链
    chain = prompt | llm | StrOutputParser()
    
    # 调用AI模型进行分析
    print("使用AI分析识别广告部分...")
    try:
        result = chain.invoke({
            "subtitle_data": json.dumps(subtitle_data, ensure_ascii=False, indent=2)
        })
        
        # 打印调试信息
        print(f"AI返回的原始结果类型: {type(result)}")
        print(f"AI返回的原始结果长度: {len(str(result)) if result else 0}")
        
        # 尝试预处理AI返回的结果，提取JSON部分
        result = result.strip()
        
        # 查找JSON数组的开始和结束位置
        start_pos = result.find('[')
        end_pos = result.rfind(']') + 1
        
        if start_pos >= 0 and end_pos > start_pos:
            # 提取JSON数组部分
            json_result = result[start_pos:end_pos]
            print(f"提取的JSON部分: {json_result[:100]}...")  # 只打印开头部分，避免过长
        else:
            # 如果没有找到JSON数组格式，可能整个响应就是JSON对象
            json_result = result
            print("未找到JSON数组标记，使用整个结果作为JSON")
            
        try:
            # 解析JSON结果
            ad_segments = json.loads(json_result)
        except json.JSONDecodeError:
            print(f"JSON解析失败，尝试用正则表达式提取...")
            # 使用正则表达式尝试提取可能的JSON对象
            import re
            pattern = r'\[\s*\{.*?\}\s*\]'
            matches = re.search(pattern, result, re.DOTALL)
            if matches:
                try:
                    json_result = matches.group(0)
                    ad_segments = json.loads(json_result)
                except:
                    print(f"正则表达式提取的内容仍无法解析为JSON")
                    ad_segments = []
            else:
                print(f"无法从AI响应中提取有效的JSON数据")
                ad_segments = []
        
        # 验证生成的广告片段
        validated_ad_segments = []
        for i, segment in enumerate(ad_segments):
            # 确保每个片段都有必需的字段
            required_fields = ["start_time", "end_time", "reason"]
            if all(k in segment for k in required_fields):
                # 计算时长
                duration = segment["end_time"] - segment["start_time"]
                segment["duration"] = round(duration, 3)
                
                # 添加序号和格式化的时间戳
                segment["id"] = i + 1
                segment["start_timestamp"] = seconds_to_timestamp(segment["start_time"])
                segment["end_timestamp"] = seconds_to_timestamp(segment["end_time"])
                
                validated_ad_segments.append(segment)
            else:
                missing = [f for f in required_fields if f not in segment]
                print(f"警告：广告片段 {i+1} 缺少必需字段：{', '.join(missing)}")
        
        print(f"AI分析完成，识别出 {len(validated_ad_segments)} 个广告片段")
        return validated_ad_segments
    
    except Exception as e:
        print(f"AI分析过程中出现错误: {str(e)}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        print(f"详细错误信息: {traceback.format_exc()}")
        return []


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="基于字幕内容的广告检测工具")
    parser.add_argument("srt_file", help="SRT字幕文件路径")
    parser.add_argument("--output", default="ads_info.json", help="输出JSON文件路径")
    
    args = parser.parse_args()
    
    # 检测广告片段
    ad_segments = detect_ads_in_subtitles(args.srt_file)
    
    # 创建结果字典
    result = {
        "srt_file": args.srt_file,
        "ad_count": len(ad_segments),
        "ad_segments": ad_segments
    }
    
    # 保存到JSON文件
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 打印简短的广告概览
    print("\n广告片段概览:")
    if ad_segments:
        for ad in ad_segments:
            duration_str = f"{ad['duration']:.1f}秒"
            print(f"  广告 {ad['id']}: {ad['start_timestamp']} - {ad['end_timestamp']} ({duration_str}) | 理由: {ad['reason']}")
    else:
        print("  未检测到广告内容")
    
    print(f"\n详细结果已保存至: {args.output}") 