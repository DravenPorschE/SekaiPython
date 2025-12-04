import pyaudio

def list_audio_devices():
    """List all available audio input and output devices"""
    pa = pyaudio.PyAudio()
    
    print("=" * 60)
    print("🎤 AVAILABLE AUDIO DEVICES")
    print("=" * 60)
    
    for i in range(pa.get_device_count()):
        device_info = pa.get_device_info_by_index(i)
        
        # Device type indicators
        input_channels = device_info['maxInputChannels']
        output_channels = device_info['maxOutputChannels']
        
        device_type = []
        if input_channels > 0:
            device_type.append(f"IN:{input_channels}")
        if output_channels > 0:
            device_type.append(f"OUT:{output_channels}")
        
        print(f"\n[{i}] {device_info['name']}")
        print(f"    Type: {'/'.join(device_type)}")
        print(f"    Default Sample Rate: {device_info['defaultSampleRate']} Hz")
        print(f"    Host API: {pa.get_host_api_info_by_index(device_info['hostApi'])['name']}")
    
    pa.terminate()

# Usage
list_audio_devices()