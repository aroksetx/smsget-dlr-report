#!/usr/bin/env python3
import base64
import pickle
import pprint

# ============
# PASTE DATA HERE
# ============

SUBMIT_SM_BILL_BASE64 = """
gAJjamFzbWluLnJvdXRpbmcuQmlsbHMKU3VibWl0U21CaWxsCnEAKYFxAX1xAihYAwAAAGJpZHED
WCQAAAA3OTZlM2Q5YS1iOTFiLTRlNjYtOGE0OC0yMGFkNzFmMTcwZTNxBFgEAAAAdXNlcnEFY2ph
c21pbi5yb3V0aW5nLmphc21pbkFwaQpVc2VyCnEGKYFxB31xCChYAwAAAHVpZHEJWA4AAAB0ZWFt
Y2x1c3NlbmRlcnEKWAUAAABncm91cHELY2phc21pbi5yb3V0aW5nLmphc21pbkFwaQpHcm91cApx
DCmBcQ19cQ4oWAMAAABnaWRxD1gHAAAAcGFybmVyc3EQWAcAAABlbmFibGVkcRGIdWJoEYhYCAAA
AHVzZXJuYW1lcRJYDgAAAHRlYW1jbHVzc2VuZGVycRNYCAAAAHBhc3N3b3JkcRRjX2NvZGVjcwpl
bmNvZGUKcRVYFwAAAMOlEzJ7wqHDo8KzWsONXsKsExcFK8KxcRZYBgAAAGxhdGluMXEXhnEYUnEZ
WA0AAABtdF9jcmVkZW50aWFscRpjamFzbWluLnJvdXRpbmcuamFzbWluQXBpCk10TWVzc2FnaW5n
Q3JlZGVudGlhbApxGymBcRx9cR0oWA4AAABhdXRob3JpemF0aW9uc3EefXEfKFgJAAAAaHR0cF9z
ZW5kcSCIWAkAAABodHRwX2J1bGtxIYlYDAAAAGh0dHBfYmFsYW5jZXEiiFgJAAAAaHR0cF9yYXRl
cSOIWAoAAABzbXBwc19zZW5kcSSIWBEAAABodHRwX2xvbmdfY29udGVudHEliFgNAAAAc2V0X2Rs
cl9sZXZlbHEmiFgTAAAAaHR0cF9zZXRfZGxyX21ldGhvZHEniFgSAAAAc2V0X3NvdXJjZV9hZGRy
ZXNzcSiIWAwAAABzZXRfcHJpb3JpdHlxKYhYEwAAAHNldF92YWxpZGl0eV9wZXJpb2RxKohYDwAA
AHNldF9oZXhfY29udGVudHEriFgaAAAAc2V0X3NjaGVkdWxlX2RlbGl2ZXJ5X3RpbWVxLIh1WA0A
AAB2YWx1ZV9maWx0ZXJzcS19cS4oWBMAAABkZXN0aW5hdGlvbl9hZGRyZXNzcS9jcmUKX2NvbXBp
bGUKcTBoFVgCAAAALipxMWgXhnEyUnEzSwCGcTRScTVYDgAAAHNvdXJjZV9hZGRyZXNzcTZoNVgI
AAAAcHJpb3JpdHlxN2gwaBVYBwAAAF5bMC0zXSRxOGgXhnE5UnE6SwCGcTtScTxYDwAAAHZhbGlk
aXR5X3BlcmlvZHE9aDBoFVgFAAAAXlxkKyRxPmgXhnE/UnFASwCGcUFScUJYBwAAAGNvbnRlbnRx
Q2g1dVgIAAAAZGVmYXVsdHNxRH1xRWg2TnNYBgAAAHF1b3Rhc3FGfXFHKFgHAAAAYmFsYW5jZXFI
TlgfAAAAZWFybHlfZGVjcmVtZW50X2JhbGFuY2VfcGVyY2VudHFJTlgPAAAAc3VibWl0X3NtX2Nv
dW50cUpOWA8AAABodHRwX3Rocm91Z2hwdXRxS0dAj0AAAAAAAFgQAAAAc21wcHNfdGhyb3VnaHB1
dHFMR0AgAAAAAAAAdVgOAAAAcXVvdGFzX3VwZGF0ZWRxTYl1YlgQAAAAc21wcHNfY3JlZGVudGlh
bHFOY2phc21pbi5yb3V0aW5nLmphc21pbkFwaQpTbXBwc0NyZWRlbnRpYWwKcU8pgXFQfXFRKGge
fXFSWAQAAABiaW5kcVOIc2hGfXFUWAwAAABtYXhfYmluZGluZ3NxVUsIc3VidWJYBwAAAGFtb3Vu
dHNxVn1xVyhYCQAAAHN1Ym1pdF9zbXFYRwAAAAAAAAAAWA4AAABzdWJtaXRfc21fcmVzcHFZRwAA
AAAAAAAAdVgHAAAAYWN0aW9uc3FafXFbWBkAAABkZWNyZW1lbnRfc3VibWl0X3NtX2NvdW50cVxL
AHN1Yi4=
"""

PAYLOAD_BASE64 = """
gAJjc21wcC5wZHUub3BlcmF0aW9ucwpTdWJtaXRTTQpxACmBcQF9cQIoWAIAAABpZHEDY3NtcHAucGR1LnBkdV90eXBlcwpDb21tYW5kSWQKcQRLCIVxBVJx
BlgGAAAAc2VxTnVtcQdOWAYAAABzdGF0dXNxCGNzbXBwLnBkdS5wZHVfdHlwZXMKQ29tbWFuZFN0YXR1cwpxCUsBhXEKUnELWAsAAABjdXN0b21fdGx2c3EM
XXENWAYAAABwYXJhbXNxDn1xDyhYCwAAAHNvdXJjZV9hZGRycRBOWBAAAABkZXN0aW5hdGlvbl9hZGRycRFjX2NvZGVjcwplbmNvZGUKcRJYBQAAADY3ODkw
cRNYBgAAAGxhdGluMXEUhnEVUnEWWA0AAABzaG9ydF9tZXNzYWdlcRdoElifAAAABQADDgIBU3VjY2VzcyAiNDUxMjFiZDMtZTFhYi00ZWU4LTllYWUtMmY4
MzU4N2ZiODVjIiBTdWNjZXNzICI0NTEyMWJkMy1lMWFiLTRlZTgtOWVhZS0yZjgzNTg3ZmI4NWMiU3VjY2VzcyAiNDUxMjFiZDMtZTFhYi00ZWU4LTllYWUt
MmY4MzU4N2ZiODVjIlN1Y2Nlc3MgIjQ1MTIxcRhoFIZxGVJxGlgLAAAAZGF0YV9jb2RpbmdxG0sAWAwAAABzZXJ2aWNlX3R5cGVxHE5YDwAAAHNvdXJjZV9h
ZGRyX3RvbnEdWAgAAABOQVRJT05BTHEeWA8AAABzb3VyY2VfYWRkcl9ucGlxH1gEAAAASVNETnEgWA0AAABkZXN0X2FkZHJfdG9ucSFYDQAAAElOVEVSTkFU
SU9OQUxxIlgNAAAAZGVzdF9hZGRyX25waXEjaCBYCQAAAGVzbV9jbGFzc3EkY3NtcHAucGR1LnBkdV90eXBlcwpFc21DbGFzcwpxJWNzbXBwLnBkdS5wZHVf
dHlwZXMKRXNtQ2xhc3NNb2RlCnEmSwGFcSdScShjc21wcC5wZHUucGR1X3R5cGVzCkVzbUNsYXNzVHlwZQpxKUsBhXEqUnErY19fYnVpbHRpbl9fCnNldApx
LF1xLWNzbXBwLnBkdS5wZHVfdHlwZXMKRXNtQ2xhc3NHc21GZWF0dXJlcwpxLksBhXEvUnEwYYVxMVJxModxM4FxNFgLAAAAcHJvdG9jb2xfaWRxNU5YDQAA
AHByaW9yaXR5X2ZsYWdxNmNzbXBwLnBkdS5wZHVfdHlwZXMKUHJpb3JpdHlGbGFnCnE3SwGFcThScTlYFgAAAHNjaGVkdWxlX2RlbGl2ZXJ5X3RpbWVxOk5Y
DwAAAHZhbGlkaXR5X3BlcmlvZHE7TlgTAAAAcmVnaXN0ZXJlZF9kZWxpdmVyeXE8Y3NtcHAucGR1LnBkdV90eXBlcwpSZWdpc3RlcmVkRGVsaXZlcnkKcT1j
c21wcC5wZHUucGR1X3R5cGVzClJlZ2lzdGVyZWREZWxpdmVyeVJlY2VpcHQKcT5LAYVxP1JxQGgsXXFBhXFCUnFDiYdxRIFxRVgXAAAAcmVwbGFjZV9pZl9w
cmVzZW50X2ZsYWdxRlgOAAAARE9fTk9UX1JFUExBQ0VxR1gRAAAAc21fZGVmYXVsdF9tc2dfaWRxSEsAWBUAAABtb3JlX21lc3NhZ2VzX3RvX3NlbmRxSWNz
bXBwLnBkdS5wZHVfdHlwZXMKTW9yZU1lc3NhZ2VzVG9TZW5kCnFKSwKFcUtScUx1WAcAAABuZXh0UGR1cU1oACmBcU59cU8oaANoBmgHTmgIaAtoDGgNaA59
cVAoaBBOaBFoFmgXaBJYgwAAAAUAAw4CAmJkMy1lMWFiLTRlZTgtOWVhZS0yZjgzNTg3ZmI4NWMiIFN1Y2Nlc3MgIjQ1MTIxYmQzLWUxYWItNGVlOC05ZWFl
LTJmODM1ODdmYjg1YyJTdWNjZXNzICI0NTEyMWJkMy1lMWFiLTRlZTgtOWVhZS0yZjgzNTg3ZmI4NWMicVFoFIZxUlJxU2gbSwBoHE5oHWgeaB9oIGghaCJo
I2ggaCRoJWgoaCtoLF1xVGgwYYVxVVJxVodxV4FxWGg1Tmg2aDloOk5oO05oPGg9aD5LAoVxWVJxWmgsXXFbhXFcUnFdiYdxXoFxX2hGaEdoSEsAaEloSksB
hXFgUnFhdXVidWIu
"""

# ============
# DECODER
# ============

def extract_sms_text(short_message):
    """Extract text from SMS short_message, handling UDH headers"""
    if not short_message:
        return ""
    
    # Check if it starts with UDH (User Data Header)
    if len(short_message) > 5 and short_message[0] == 0x05:
        # Skip UDH: first byte is length, then skip that many bytes + 1
        udh_length = short_message[0]
        text_start = udh_length + 1
        return short_message[text_start:].decode('utf-8', errors='ignore')
    else:
        return short_message.decode('utf-8', errors='ignore')

def decode_pickle(label, b64):
    print(f"\n===== {label} =====")
    raw = None
    try:
        raw = base64.b64decode(b64)
        print(f"Base64 decoded successfully: {len(raw)} bytes")
        obj = pickle.loads(raw)
        pprint.pprint(obj)
        
        # Try to show more details about the object
        if hasattr(obj, '__dict__'):
            print("\n--- Object attributes ---")
            for key, value in obj.__dict__.items():
                print(f"{key}: {value}")
        
        # Special handling for SMS PDUs to show full message
        if hasattr(obj, 'params') and 'short_message' in obj.params:
            print(f"\n--- SMS MESSAGE RECONSTRUCTION ---")
            
            parts = []
            current_pdu = obj
            part_num = 1
            
            while current_pdu:
                if hasattr(current_pdu, 'params') and 'short_message' in current_pdu.params:
                    short_msg = current_pdu.params['short_message']
                    text = extract_sms_text(short_msg)
                    print(f"Part {part_num}: {text}")
                    parts.append(text)
                
                # Check for next PDU
                current_pdu = getattr(current_pdu, 'nextPdu', None)
                part_num += 1
            
            if len(parts) > 1:
                full_message = ''.join(parts)
                print(f"\n--- COMPLETE MESSAGE ---")
                print(f"Full message ({len(parts)} parts): {full_message}")
            
        return obj
    except EOFError as e:
        print(f"EOFError: {e}")
        print("The pickle data appears to be truncated or incomplete.")
        if raw:
            print(f"Raw data length: {len(raw)} bytes")
            print(f"Last 20 bytes: {raw[-20:]}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    decode_pickle("SUBMIT_SM_BILL", SUBMIT_SM_BILL_BASE64)
    decode_pickle("PAYLOAD (SubmitSM)", PAYLOAD_BASE64)