# Option 2: Using reference audio
from fish_audio_sdk import Session, TTSRequest, ReferenceAudio


api_key = "ed0df68c39384dcfa1c2c9be7b90e8f2"

text = """
On the tank, these were in the rear.

These new high-performance tractors proved to be significantly more adept, and were capable of towing substantial trailers laden with fuel.

And notably, fuel was the utmost importance in Antarctica, constituting between 70 to 75 percent of all of the transported cargo. It was used not only for the fuel for the vehicles, but also as the only reliable source of heat to keep people from freezing to death.

The expedition's remarkable logistical support facilitated the establishment of two additional research stations that continued to operate up until 2019.

Ultimately, this mission concluded its endeavors and returned back home in 1958, leaving a lasting impact on the Antarctica Research and Exploration Mission.

But these tank tractors, whilst brilliant, still had some major flaws. You see, while much of the mid-coast had been explored, in the heart of Antarctica, the weather could escalate to even more extreme conditions, and had stopped the Soviets from getting much inland.

In certain ATTs, occupants found themselves compelled to ignite fires beneath the vehicle to prevent the diesel fuel from solidifying due to the frigid temperatures. And by freezing, I mean that they would have to chop up the fuel like firewood to get it back into the engine.
"""

# 基本使用（不使用参考音频）
def text_to_speech(text, api_key, reference_audio_path=None, output_path="output.mp3", reference_text=None):
    """
    将文本转换为语音
    
    参数:
        text (str): 要转换的文本内容
        api_key (str): Fish Audio SDK的API密钥
        reference_audio_path (str, 可选): 参考音频文件路径，用于模仿语音风格
        output_path (str, 可选): 输出音频文件路径，默认为'output.mp3'
        reference_text (str, 可选): 参考音频对应的文本，当使用参考音频时必须提供
        
    返回:
        str: 输出音频文件路径
    """
    session = Session(api_key)
    
    # 准备TTS请求
    tts_request_params = {"text": text}
    
    # 如果提供了参考音频
    if reference_audio_path:
        if not reference_text:
            raise ValueError("使用参考音频时必须提供参考文本(reference_text)")
            
        with open(reference_audio_path, "rb") as audio_file:
            reference = ReferenceAudio(
                audio=audio_file.read(),
                text=reference_text
            )
            tts_request_params["references"] = [reference]
    
    # 创建TTS请求
    request = TTSRequest(**tts_request_params)
    
    # 生成语音并保存到文件
    with open(output_path, "wb") as f:
        for chunk in session.tts(request):
            f.write(chunk)
            
    return output_path

# 使用参考音频
text_to_speech(
    text="这是一个测试文本，将使用参考音频的语音风格。",
    api_key=api_key,
    reference_audio_path="luyin.mp3",
    output_path="我的语音.mp3",
    reference_text="当苏联将坦克与南极洲的冰原相结合，会发生什么？你将得到可能是人类史上最疯狂的陆地载具。它能在零下57摄氏度（-70华氏度）的环境中工作，穿越暴风雪运输大宗货物，同时为乘员提供舒适的居住空间。与早期美国征服南极的尝试不同，俄罗斯人实际研发了多个迭代版本，其最新型号甚至在本世纪仍在服役。这就是苏联南极坦克的故事——在美国人失败的地方，他们成功了。来自哈尔科夫的传奇——哈尔科夫尚卡。"
)