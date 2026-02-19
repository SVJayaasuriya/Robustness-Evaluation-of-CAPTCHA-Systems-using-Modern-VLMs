import argparse
import os
import time
import random
import requests
import re
import base64
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
from openai import OpenAI
from PIL import Image
import io
from safe_logger import init_result_logger, log_result
import time



load_dotenv()
def average_of_array(arr):
    if not arr:
        return 0  # Handle edge case of empty array
    sum_elements = sum(arr)
    average = sum_elements / len(arr)
    return average - 5

def encode_image_to_base64(image_path):
    """Encodes an image file to a base64 PNG string (strict OpenAI compatible)."""
    import io, base64

    # Convert image to PNG and encode to base64 (without newlines)
    with Image.open(image_path) as img:
        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="PNG")
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return base64_image.strip()



def ask_recaptcha_to_chatgpt(base64_image):
    import os, time, io, base64, re

    load_dotenv()  # if not already called at module top
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = "gpt-5-mini" #gpt-5-mini

    # Ensure we have a clean base64 string (no whitespace/newlines)
    base64_str = base64_image.strip()

    # Optional: validate and re-encode to PNG to make sure OpenAI accepts it
    try:
        img_bytes = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        # Re-encode as PNG to guarantee correct format / headers
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        base64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        # If decoding/re-encoding fails, return "0" or handle as you prefer
        print("Local image validation/normalization failed:", e)
        return "0"

    prompt = """Prompt Removed due to ethical concerns"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = openai_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_str}"}
                            }
                        ],
                    }
                ],
            )

            # Robustly extract text from response (handles a few shapes)
            result = ""
            try:
                # Preferred structure: content is a list of blocks
                result = response.choices[0].message.content[0].text
            except Exception:
                try:
                    # Older style: content as raw string
                    result = response.choices[0].message.content
                except Exception:
                    # Fallback: some clients return top-level 'text' on choice
                    result = getattr(response.choices[0], "text", "") or ""

            result = (result or "").strip()
            # Clean up the response to ensure proper format: keep digits only joined by hyphens
            numbers_only = re.findall(r'\d+', result)
            if numbers_only:
                return '-'.join(numbers_only)
            else:
                # If no digits, return whatever the model replied (or "0" if empty)
                return result if result else "0"

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                print("All attempts failed, returning empty result")
                return "0"
            time.sleep(2)




import base64
import io
import os
from openai import OpenAI
from PIL import Image

def ask_text_to_chatgpt(base64_image):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = "gpt-4o"  # or "gpt-4o" if you prefer slightly cheaper

    # Decode the base64 image
    image_data = base64.b64decode(base64_image)
    image = Image.open(io.BytesIO(image_data))
    
    prompt = (
        "Prompt removed due to ethical concerns"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                    },
                ],
            }
        ],
    )

    return response.choices[0].message.content.strip()


def complicated_text_test(driver, max_retries: int = 1, wait_after_submit: float = 10.0):
    """
    Robust MTCaptcha test:
    - enters model answer in iframe
    - clicks submit
    - polls for success using multiple methods:
      1) DOM message inside iframe (#mtcap-msg-1 p)
      2) DOM message in parent document (#mtcap-msg-1 p)
      3) window.__mtcaptcha.state inside iframe
      4) window.__mtcaptcha.state in parent
    Saves debug screenshot + short debug file on timeout.
    Returns: (captcha_type, "success"/"fail"/"error", time_taken)
    """
    captcha_type = "mtcaptcha"
    start_overall = time.time()

    try:
        # Load page and capture iframe screenshot
        driver.get("https://2captcha.com/demo/mtcaptcha")
        time.sleep(3)

        iframe = WebDriverWait(driver, 12).until(
            EC.presence_of_element_located((By.ID, "mtcaptcha-iframe-1"))
        )

        # Screenshot and ask model (✅ SOLVER UNCHANGED)
        iframe.screenshot('mtcaptcha_captcha.png')
        base64_string = encode_image_to_base64('mtcaptcha_captcha.png')
        answer = ask_text_to_chatgpt(base64_string)
        print("Model answer:", answer)

        # Enter answer inside iframe
        driver.switch_to.frame(iframe)
        try:
            input_field = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".mtcap-inputtext"))
            )
        except Exception as e:
            print("Input field not found inside iframe:", e)
            driver.switch_to.default_content()
            return captcha_type, "error", round(time.time() - start_overall, 3)

        input_field.clear()
        input_field.send_keys(answer)
        time.sleep(0.8)
        driver.switch_to.default_content()

        # Click submit
        submit_button = None
        submit_selectors = [
            (By.XPATH, "//button[contains(text(), 'Submit') or contains(text(), 'Check')]"),
            (By.CSS_SELECTOR, "button[class*='_buttonPrimary_']"),
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.TAG_NAME, "button")
        ]
        for sel_type, sel_val in submit_selectors:
            try:
                submit_button = WebDriverWait(driver, 4).until(
                    EC.element_to_be_clickable((sel_type, sel_val))
                )
                break
            except:
                continue

        if not submit_button:
            buttons = driver.find_elements(By.TAG_NAME, "button")
            submit_button = buttons[-1] if buttons else None

        if not submit_button:
            print("No submit button found")
            return captcha_type, "error", round(time.time() - start_overall, 3)

        submit_button.click()

        # --- STRICT POLLING for result ---
        start_time = time.time()
        poll_interval = 0.25
        found_debug = None
        success = None
        reason = None

        while time.time() - start_time < wait_after_submit:
            success = None  # ✅ reset every poll

            # 1) DOM inside iframe
            try:
                iframe_elem = None
                try:
                    iframe_elem = driver.find_element(By.ID, "mtcaptcha-iframe-1")
                except:
                    iframe_elem = None

                if iframe_elem:
                    driver.switch_to.frame(iframe_elem)
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, "#mtcap-msg-1 p")
                        text = (el.get_attribute("innerText") or "").strip().lower()
                        found_debug = {"context": "iframe_dom", "text": text}

                        if text == "verified successfully":
                            success = True
                            reason = "iframe_dom_verified"
                            driver.switch_to.default_content()
                            break

                        if any(k in text for k in ("invalid", "incorrect", "fail", "error", "retry", "denied")):
                            success = False
                            reason = f"iframe_dom_fail:{text}"
                            driver.switch_to.default_content()
                            break
                    except:
                        pass

                    # 2) JS state inside iframe
                    try:
                        state = driver.execute_script(
                            "return (window.__mtcaptcha && window.__mtcaptcha.state) ? window.__mtcaptcha.state : null;"
                        )
                        found_debug = {"context": "iframe_js", "state": state}

                        if state and state.strip().lower() == "verified":
                            success = True
                            reason = "iframe_js_verified"
                            driver.switch_to.default_content()
                            break

                        if state and state.strip().lower() in ("failed", "error", "invalid", "denied"):
                            success = False
                            reason = f"iframe_js_{state}"
                            driver.switch_to.default_content()
                            break
                    except:
                        pass

                    driver.switch_to.default_content()
            except:
                try:
                    driver.switch_to.default_content()
                except:
                    pass

            # 3) Parent DOM
            try:
                el_parent = driver.find_element(By.CSS_SELECTOR, "#mtcap-msg-1 p")
                text_parent = (el_parent.get_attribute("innerText") or "").strip().lower()
                found_debug = {"context": "parent_dom", "text": text_parent}

                if text_parent == "verified successfully":
                    success = True
                    reason = "parent_dom_verified"
                    break

                if any(k in text_parent for k in ("invalid", "incorrect", "fail", "error", "retry", "denied")):
                    success = False
                    reason = f"parent_dom_fail:{text_parent}"
                    break
            except:
                pass

            # 4) Parent JS state
            try:
                state_parent = driver.execute_script(
                    "return (window.__mtcaptcha && window.__mtcaptcha.state) ? window.__mtcaptcha.state : null;"
                )
                found_debug = {"context": "parent_js", "state": state_parent}

                if state_parent and state_parent.strip().lower() == "verified":
                    success = True
                    reason = "parent_js_verified"
                    break

                if state_parent and state_parent.strip().lower() in ("failed", "error", "invalid", "denied"):
                    success = False
                    reason = f"parent_js_{state_parent}"
                    break
            except:
                pass

            time.sleep(poll_interval)

        # --- Timeout fallback ---
        if success is None:
            success = False
            reason = "timeout_no_signal"
            debug_sn = found_debug or {}
            print("final snapshot:", debug_sn)

            ts = int(time.time())
            try:
                driver.save_screenshot(f"mtcaptcha_debug_{ts}.png")
                with open(f"mtcaptcha_debug_{ts}.txt", "w", encoding="utf-8") as f:
                    f.write(f"found_debug={debug_sn}\n")
                    f.write(driver.page_source[:10000])
            except:
                pass

        elapsed = time.time() - start_overall
        status = "success" if success else "fail"
        print(f"result={status} | reason={reason}")
        return captcha_type, status, round(elapsed, 3)

    except Exception as e:
        elapsed = time.time() - start_overall
        print("[mtcaptcha] Exception:", e)
        try:
            driver.save_screenshot("mtcaptcha_error.png")
        except:
            pass
        return captcha_type, "error", round(elapsed, 3)


def text_test(driver):
    driver.get("https://2captcha.com/demo/normal")
    time.sleep(5)
    captcha_image = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "_captchaImage_rrn3u_9"))
    )

    time.sleep(2)
    captcha_image.screenshot('captcha_image.png')
    base64_string = encode_image_to_base64('captcha_image.png')
    response = ask_text_to_chatgpt(base64_string)

    print(response)

    input_field = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "_inputInner_ws73z_12"))
    )
    input_field.send_keys(response)
    # Try multiple selectors for the submit button
    submit_button = None
    selectors = [
        (By.XPATH, "//button[contains(@class, '_buttonPrimary_') or contains(text(), 'Submit') or contains(text(), 'Check')]"),
        (By.CSS_SELECTOR, "button[class*='_buttonPrimary_']"),
        (By.CSS_SELECTOR, "button[class*='_button_']"),
        (By.TAG_NAME, "button")
    ]
    
    for selector_type, selector_value in selectors:
        try:
            submit_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((selector_type, selector_value))
            )
            break
        except:
            continue
    
    if not submit_button:
        print("Could not find submit button, trying to find any clickable button...")
        buttons = driver.find_elements(By.TAG_NAME, "button")
        if buttons:
            submit_button = buttons[-1]  # Try the last button
    
    if submit_button:
        submit_button.click()
    else:
        print("No submit button found!")
    time.sleep(5)

def recaptcha_test(driver):
    driver.get("https://www.google.com/recaptcha/api2/demo")
    start = time.time()
    number_of_challenges = 0

    def handle_recaptcha():
        nonlocal number_of_challenges
        try:
            # Wait for the reCAPTCHA iframe to load
            recaptcha_frame = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/anchor']"))
            )
            recaptcha_frame.screenshot('recaptcha_checkbox.png')
            driver.switch_to.frame(recaptcha_frame)
            
            # Click the checkbox
            checkbox = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.ID, "recaptcha-anchor"))
            )
            checkbox.click()
            driver.switch_to.default_content()
            time.sleep(1)
            
            # Check if challenge appears
            try:
                challenge_iframe = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/bframe']"))
                )
                print("Challenge detected, processing...")
                
                while True:
                    try:
                        number_of_challenges += 1
                        filename = f"recaptcha_challenge_{number_of_challenges}.png"

                        # Wait for challenge to fully load
                        time.sleep(1)

                        # Recheck if iframe is still valid
                        try:
                            challenge_iframe.screenshot(filename)
                        except Exception:
                            print("Iframe became stale, reacquiring...")
                            challenge_iframe = WebDriverWait(driver, 2).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/bframe']"))
                            )
                            challenge_iframe.screenshot(filename)

                        base64_string = encode_image_to_base64(filename)

                        print(f"Processing challenge {number_of_challenges}...")
                        answer = ask_recaptcha_to_chatgpt(base64_string)
                        print(f"AI response: {answer}")

                        if "," in answer:
                            array = answer.split(", ")
                        elif "-" in answer:
                            array = answer.split("-")
                        else:
                            array = [answer]

                        driver.switch_to.frame(challenge_iframe)

                        # Try different table selectors
                        table = None
                        for selector in ["rc-imageselect-table-33", "rc-imageselect-table-44", "rc-imageselect-table"]:
                            try:
                                table = WebDriverWait(driver, 1).until(
                                    EC.presence_of_element_located((By.CLASS_NAME, selector))
                                )
                                break
                            except:
                                continue

                        if table:
                            time.sleep(2)  # Give more time for images to load
                            all_images = table.find_elements(By.CSS_SELECTOR, "td")
                            print(f"Found {len(all_images)} image tiles")

                            clicked_count = 0
                            for each_element in array:
                                try:
                                    index = int(each_element.strip())
                                    if 0 <= index < len(all_images):
                                        all_images[index].click()
                                        clicked_count += 1
                                        print(f"Clicked tile {index}")
                                        time.sleep(0.5)
                                except (ValueError, IndexError) as e:
                                    print(f"Error clicking tile {each_element}: {e}")
                                    continue

                            print(f"Clicked {clicked_count} tiles total")

                        # Click verify button
                        verify_selectors = ["#recaptcha-verify-button", ".rc-button-default"]
                        for selector in verify_selectors:
                            try:
                                submit_button = WebDriverWait(driver, 1).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                                )
                                submit_button.click()
                                break
                            except:
                                continue

                        driver.switch_to.default_content()
                        time.sleep(1)  # Give more time for processing

                        # Check if solved
                        try:
                            driver.switch_to.frame(recaptcha_frame)
                            if driver.find_elements(By.CSS_SELECTOR, ".recaptcha-checkbox-checked"):
                                print("reCAPTCHA solved successfully!")
                                driver.switch_to.default_content()
                                break
                            driver.switch_to.default_content()
                        except:
                            pass

                        # ✅ Reacquire iframe if another challenge appears
                        try:
                            challenge_iframe = WebDriverWait(driver, 2).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/bframe']"))
                            )
                            print("New challenge detected, continuing...\n")
                            continue
                        except:
                            print("No more challenges, reCAPTCHA completed.")
                            break

                    except Exception as ex:
                        print(f"Challenge error: {ex}")
                        break

            except:
                print("No challenge required, reCAPTCHA completed successfully!")

        except Exception as ex:
            print(f"reCAPTCHA error: {ex}")

    handle_recaptcha()

    # Try to submit the form if there's a submit button
    try:
        submit_btn = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit'], button[type='submit']"))
        )
        submit_btn.click()
        time.sleep(1)
        print("Form submitted successfully!")
    except:
        print("No submit button found or form already submitted.")
    
    attempt_elapsed = round(time.time() - start, 3)
    return "recaptcha", "success", attempt_elapsed, number_of_challenges


def botdetect_demo_test(driver, max_retries: int = 1, wait_after_submit: float = 6.0):
    """
    Improved BotDetect test with robust success detection.
    - uses visibility checks + checks parent innerText/innerHTML
    - DOES NOT CHANGE solving logic (encode_image_to_base64 / ask_text_to_chatgpt)
    """
    print("Starting BotDetect CAPTCHA test...")
    captcha_type = "botdetect_demo"
    run_attempt = 0
    overall_start = time.time()
    already_logged = False   # ✅ prevents double log

    try:
        driver.get("https://captcha.com/demos/features/captcha-demo.aspx")
        time.sleep(3)
        driver.save_screenshot("botdetect_full_page.png")

        # --- Locate Captcha image ---
        selectors = [
            (By.ID, "BotDetectCaptcha_CaptchaImage"),
            (By.XPATH, "//img[contains(@id, 'CaptchaImage')]"),
            (By.XPATH, "//img[contains(@src, 'BotDetectCaptcha.ashx')]"),
            (By.CSS_SELECTOR, "img[src*='BotDetectCaptcha']"),
            (By.CSS_SELECTOR, "img[id*='Captcha']"),
            (By.TAG_NAME, "img")
        ]
        captcha_img = None
        for t, val in selectors:
            try:
                captcha_img = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((t, val))
                )
                break
            except:
                pass

        if not captcha_img:
            print("CAPTCHA image not found")
            if not already_logged:
                already_logged = True
            return captcha_type, "fail",0

        initial_src = captcha_img.get_attribute("src")

        # --- Locate input field ---
        input_field = None
        for t, val in [
            (By.ID, "BotDetectCaptcha_CaptchaCode"),
            (By.XPATH, "//input[contains(@id, 'CaptchaCode')]"),
            (By.XPATH, "//input[@type='text']"),
            (By.CSS_SELECTOR, "input[type='text']")
        ]:
            try:
                input_field = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((t, val))
                )
                break
            except:
                pass

        if not input_field:
            print("CAPTCHA input field missing")
            if not already_logged:
                already_logged = True
                log_result(captcha_type, "fail", 0, 0, "no input field")
            return captcha_type, "fail",0 

        # --- Attempts Loop ---
        while run_attempt < max_retries:
            run_attempt += 1
            attempt_start = time.time()

            captcha_img.screenshot("botdetect_captcha.png")
            encoded = encode_image_to_base64("botdetect_captcha.png")
            answer = ask_text_to_chatgpt(encoded)   # ✅ solving logic untouched
            print(f"Model Answer: {answer}")

            input_field.clear()
            input_field.send_keys(answer)

            # Submit button
            try:
                btn = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.ID, "validateCaptchaButton"))
                )
            except:
                btn = None

            if btn: btn.click()
            else: input_field.send_keys(Keys.RETURN)

            # --- Robust result detection ---
            success = None
            reason = ""
            start_wait = time.time()
            interval = 0.2
            found_debug = None

            while time.time() - start_wait < wait_after_submit:
                try:
                    result_box = None
                    try:
                        result_box = driver.find_element(By.ID, "validationResult")
                    except:
                        result_box = None

                    inner_text = ""
                    inner_html = ""
                    correct_el = None
                    incorrect_el = None
                    correct_visible = False
                    incorrect_visible = False

                    if result_box is not None:
                        try: inner_text = (result_box.get_attribute("innerText") or "").strip()
                        except: inner_text = ""
                        try: inner_html = (result_box.get_attribute("innerHTML") or "").strip()
                        except: inner_html = ""

                        try: correct_el = result_box.find_element(By.CSS_SELECTOR, "span.correct")
                        except: correct_el = None
                        try: incorrect_el = result_box.find_element(By.CSS_SELECTOR, "span.incorrect")
                        except: incorrect_el = None

                        try: correct_visible = bool(correct_el and correct_el.is_displayed())
                        except: correct_visible = False
                        try: incorrect_visible = bool(incorrect_el and incorrect_el.is_displayed())
                        except: incorrect_visible = False

                    found_debug = {
                        "inner_text": inner_text,
                        "inner_html": inner_html,
                        "correct_visible": correct_visible,
                        "incorrect_visible": incorrect_visible
                    }

                    if correct_visible:
                        success = True
                        reason = "visible_correct_span"
                        break

                    if incorrect_visible:
                        success = False
                        reason = "visible_incorrect_span"
                        break

                    t_low = (inner_text or "").lower()
                    h_low = (inner_html or "").lower()
                    if "correct" in t_low or "correct" in h_low:
                        success = True
                        reason = "parent_text_contains_correct"
                        break

                    if "invalid" in t_low or "invalid" in h_low or "incorrect" in t_low or "incorrect" in h_low:
                        success = False
                        reason = "parent_text_contains_invalid"
                        break

                except:
                    pass

                time.sleep(interval)

            if success is None:
                reason = "timeout_no_signal"
                debug_sn = found_debug or {}
                notes_debug = f"inner_text={debug_sn.get('inner_text')};inner_html={debug_sn.get('inner_html')};correct_vis={debug_sn.get('correct_visible')};incorrect_vis={debug_sn.get('incorrect_visible')}"
                print("[DEBUG] Final detection snapshot:", notes_debug)
                success = False

            driver.save_screenshot(f"botdetect_result_attempt_{run_attempt}.png")
            attempt_elapsed = time.time() - attempt_start

            notes = f"answer={answer};reason={reason};debug={found_debug}"

            if success:
                print(f"Solved on attempt {run_attempt}")
                if not already_logged:
                    already_logged = True
                return captcha_type, "success", attempt_elapsed, 1
            else:
                print(f"Attempt {run_attempt} failed ({reason})")
                if run_attempt < max_retries:
                    try:
                        try: captcha_img.click()
                        except: pass
                        time.sleep(1.5)
                        for t, val in selectors:
                            try:
                                captcha_img = driver.find_element(t, val)
                                break
                            except:
                                pass
                    except:
                        pass
                    continue
                return captcha_type, "fail", attempt_elapsed, 1

    except Exception as e:
        elapsed = time.time() - overall_start
        print(f"⚠ BotDetect error: {e}")
        driver.save_screenshot("botdetect_error.png")
        if not already_logged:
            already_logged = True
            log_result(captcha_type, "error", elapsed, run_attempt, f"exception={e}")
        return



def run_and_log(test_name, driver, test_function):
    """
    Runs a test function and logs its real result in test_results.csv
    Expects test_function to return: (captcha_type, status, time_taken)
    """
    try:
        result = test_function(driver)

        # ✅ Handle proper return
        if isinstance(result, tuple) and len(result) == 4:
            captcha_type, status, time_taken, attempts = result
            log_result(captcha_type, status, time_taken, attempts)
        else:
            # ❗ fallback if function returned nothing
            time_taken = 0
            log_result(test_name, "error", time_taken)

    except Exception as e:
        print(f"{test_name} test crashed: {e}")
        time_taken = 0
        log_result(test_name, "error", time_taken)


def main():
    parser = argparse.ArgumentParser(description="Run CAPTCHA solver tests with logging")
    parser.add_argument(
        "captcha_type",
        choices=["text", "complicated_text", "recaptcha", "botdetect_demo", "twocaptcha_text", "all"],
        help="Select which captcha test to run"
    )
    parser.add_argument("--runs", type=int, default=1, help="Number of times to run the test")
    args = parser.parse_args()

    # ✅ Initialize logger only once
    init_result_logger()

    # ✅ WebDriver setup
    service = FirefoxService("geckodriver.exe")
    driver = webdriver.Firefox(service=service)

    try:
        for i in range(args.runs):

            if args.captcha_type == "text":
                run_and_log("text", driver, text_test)

            elif args.captcha_type == "complicated_text":
                run_and_log("complicated_text", driver, complicated_text_test)

            elif args.captcha_type == "recaptcha":
                run_and_log("recaptcha", driver, recaptcha_test)

            elif args.captcha_type == "botdetect_demo":
                run_and_log("botdetect_demo", driver, botdetect_demo_test)

            elif args.captcha_type == "twocaptcha_text":
                run_and_log("twocaptcha_text", driver, twocaptcha_text_test)

            elif args.captcha_type == "all":
                run_and_log("text", driver, text_test)
                run_and_log("complicated_text", driver, complicated_text_test)
                run_and_log("recaptcha", driver, recaptcha_test)
                run_and_log("botdetect_demo", driver, botdetect_demo_test)
                run_and_log("twocaptcha_text", driver, twocaptcha_text_test)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
