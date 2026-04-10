"""Archive Ox batch automation core — Selenium driver.

Extracted from the original ArchiveOx_Automate project.
tkinter references removed; all errors are logged and surfaced
via return values so the caller (PySide6 panel) can display them.
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
import shutil
from pathlib import Path
import json
import logging
import re
import datetime

class ArchiveOxAutomator:
    def __init__(self):
        self.setup_logging()
        self.driver = None
        self.processed_files = []
        
    def setup_logging(self):
        """Setup logging for tracking operations"""
        import os
        
        # Get the directory where the script is running
        script_dir = os.path.dirname(os.path.abspath(__file__)) if __file__ else os.getcwd()
        log_file = os.path.join(script_dir, 'archive_ox_automation.log')
        
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='w'  # Overwrite log file each run
        )
        
        # Also log to console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"Log file location: {log_file}")
        print(f"Log file will be saved to: {log_file}")
    
    def setup_driver(self):
        """Initialize Chrome driver with appropriate options"""
        chrome_options = Options()
        # Remove headless mode so you can see what's happening
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Use WebDriverManager to automatically download and manage ChromeDriver
        try:
            chromedriver_path = ChromeDriverManager().install()
            self.logger.info(f"Using ChromeDriver at: {chromedriver_path}")
        except Exception as e:
            error_msg = f"Failed to setup ChromeDriver: {str(e)}"
            self.logger.error(error_msg)
            return False
        
        service = Service(chromedriver_path)
        
        try:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            return True
        except Exception as e:
            self.logger.error(f"Failed to setup driver: {str(e)}")
            return False
    
    def login_to_archive_ox(self, username, password):
        """Navigate to Archive Ox and log in"""
        try:
            self.logger.info("Starting login process...")
            
            # Navigate to Archive Ox main page
            self.driver.get("https://archiveox.com")
            self.logger.info("Navigated to archiveox.com")
            
            # Wait for the page to load
            time.sleep(5)
            
            # Debug: Print current page info
            current_url = self.driver.current_url
            page_title = self.driver.title
            self.logger.info(f"Current URL: {current_url}")
            self.logger.info(f"Page title: {page_title}")
            
            # Handle any error popups first
            try:
                # Look for error popup and dismiss it
                error_popup = self.driver.find_element(By.XPATH, "//button[contains(text(), 'OK')] | //button[@class='close'] | //*[contains(@class, 'modal')]//button")
                error_popup.click()
                self.logger.info("Dismissed error popup")
                time.sleep(2)
            except:
                self.logger.info("No error popup found")
            
            # Look for "Sign in" button on the main page
            try:
                self.logger.info("Looking for Sign in button...")
                
                # Wait a bit longer for page to fully load
                time.sleep(3)
                
                # Try multiple approaches to find the sign in link
                sign_in_button = None
                
                # Approach 1: Look for exact text "Sign in"
                try:
                    sign_in_button = self.driver.find_element(By.XPATH, "//*[text()='Sign in']")
                    self.logger.info("Found sign in with exact text match")
                except:
                    pass
                
                # Approach 2: Look for links/buttons containing "Sign"
                if not sign_in_button:
                    try:
                        sign_in_button = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Sign')] | //button[contains(text(), 'Sign')]")
                        self.logger.info("Found sign in with contains text")
                    except:
                        pass
                
                # If we found a sign in button, click it
                if sign_in_button:
                    self.logger.info(f"Sign in button found: {sign_in_button.tag_name} with text: '{sign_in_button.text}'")
                    sign_in_button.click()
                    self.logger.info("Clicked Sign in button")
                    time.sleep(3)
                else:
                    self.logger.warning("Could not find Sign in button with any method")
                    # Let's try to navigate directly to login page
                    self.logger.info("Trying direct navigation to login page")
                    self.driver.get("https://archiveox.com/login")
                    time.sleep(3)
                    
            except Exception as e:
                self.logger.warning(f"Error finding sign in button: {str(e)}")
                # Try navigating directly to login page
                self.logger.info("Trying direct navigation to login page")
                self.driver.get("https://archiveox.com/login")
                time.sleep(3)
            
            # Look for email/username field on login page
            try:
                self.logger.info("Looking for login form fields...")
                
                # Wait for form to be visible and interactable
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='email' or @type='text']"))
                )
                
                # Find email field - based on the login form structure
                email_field = self.driver.find_element(By.XPATH, "//input[@type='email']")
                self.logger.info("Found email field")
                
                email_field.clear()
                email_field.send_keys(username)
                self.logger.info("Entered email")
                
                # Find password field
                password_field = self.driver.find_element(By.XPATH, "//input[@type='password']")
                self.logger.info("Found password field")
                
                password_field.clear()
                password_field.send_keys(password)
                self.logger.info("Entered password")
                
                # Find and click the "Log in" button - be more specific
                self.logger.info("Looking for Log in button...")
                
                try:
                    # Wait a moment for any JavaScript to load
                    time.sleep(2)
                    
                    # Try to find the specific "Log in" button
                    login_button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[text()='Log in']"))
                    )
                    self.logger.info("Found 'Log in' button")
                    
                    # Scroll to button to ensure it's visible
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", login_button)
                    time.sleep(1)
                    
                    # Click the button using JavaScript to ensure it works
                    self.driver.execute_script("arguments[0].click();", login_button)
                    self.logger.info("Clicked 'Log in' button using JavaScript")
                    
                except Exception as button_error:
                    self.logger.warning(f"Could not find/click Log in button: {str(button_error)}")
                    
                    # Fallback: try pressing Enter on password field
                    try:
                        password_field.send_keys(Keys.RETURN)
                        self.logger.info("Pressed Enter on password field as fallback")
                    except Exception as enter_error:
                        self.logger.error(f"Failed to submit login form: {str(enter_error)}")
                        return False
                
                # Wait for login to complete - look for dashboard indicators
                self.logger.info("Waiting for login to complete...")
                
                # Wait a bit for the form submission to process
                time.sleep(5)
                
                # Try more flexible login success detection
                try:
                    # Wait up to 15 seconds for any of these success indicators
                    WebDriverWait(self.driver, 15).until(
                        EC.any_of(
                            # URL changes away from login
                            lambda driver: "login" not in driver.current_url.lower(),
                            # Common success indicators
                            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Hi,') or contains(text(), 'Welcome') or contains(text(), 'Dashboard')]")),
                            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Current Project') or contains(text(), 'Projects')]")),
                            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Records') or contains(text(), 'Upload')]")),
                            # URL indicators
                            EC.url_contains("dashboard"),
                            EC.url_contains("projects"),
                            EC.url_contains("app"),
                        )
                    )
                except Exception as wait_error:
                    self.logger.error(f"Login completion detection failed: {str(wait_error)}")
                    
                    # Final check - if URL changed from login, assume success
                    final_url = self.driver.current_url
                    if "login" not in final_url.lower():
                        self.logger.info("URL changed from login page - assuming successful login")
                    else:
                        self.logger.error("Login appears to have failed - still on login page")
                        return False
                
                # Debug: Check final page after login
                final_url = self.driver.current_url
                final_title = self.driver.title
                self.logger.info(f"After login - URL: {final_url}")
                self.logger.info(f"After login - Title: {final_title}")
                
                self.logger.info("Successfully logged in to Archive Ox")
                return True
                
            except Exception as login_error:
                # Check if we got an error message on the login page
                try:
                    error_messages = self.driver.find_elements(By.XPATH, 
                        "//*[contains(text(), 'Invalid') or contains(text(), 'incorrect') or contains(text(), 'error') or contains(@class, 'error')]")
                    if error_messages:
                        error_text = error_messages[0].text
                        self.logger.error(f"Login error message: {error_text}")
                        return False
                except:
                    pass
                
                self.logger.error(f"Login failed: {str(login_error)}")
                return False
            
        except Exception as e:
            self.logger.error(f"Navigation failed: {str(e)}")
            return False
    
    def select_project(self, project_name):
        """Select a project from the dropdown"""
        try:
            if not project_name:
                self.logger.info("No project specified, using current project")
                return True
            
            # Check if we're already in the correct project by looking at the page
            try:
                # Look for project name in the current page
                current_project_elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{project_name}')]")
                if current_project_elements:
                    self.logger.info(f"Already in project: {project_name} (found in page content)")
                    return True
            except:
                pass
                
            # Look for the project dropdown - fix the XPath syntax
            try:
                project_dropdown = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//button[contains(text(), '{project_name}') or contains(@aria-label, '{project_name}')]"))
                )
                
                # If we're already in the right project, no need to change
                if project_name.upper() in project_dropdown.text.upper():
                    self.logger.info(f"Already in project: {project_name}")
                    return True
                
                # Click the dropdown to see options
                project_dropdown.click()
                time.sleep(2)
                
                # Look for the project option
                project_option = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//*[contains(text(), '{project_name}')]"))
                )
                project_option.click()
                
                # Wait for project to load
                time.sleep(3)
                self.logger.info(f"Successfully selected project: {project_name}")
                return True
                
            except Exception as dropdown_error:
                self.logger.warning(f"Could not find/use project dropdown: {str(dropdown_error)}")
                # If we can't find the dropdown but we're already in the right project, that's OK
                self.logger.info(f"Assuming already in correct project: {project_name}")
                return True
            
        except Exception as e:
            self.logger.error(f"Failed to select project '{project_name}': {str(e)}")
            # Don't fail completely - assume we're in the right project
            self.logger.info(f"Continuing anyway, assuming we're in project: {project_name}")
            return True
    
    def navigate_to_records(self):
        """Navigate to the Records section and prepare for new record creation"""
        try:
            self.logger.info("Looking for Records button/link...")
            
            # Wait a bit for dashboard to fully load
            time.sleep(3)
            
            # Try to find the specific Records button we want
            records_element = None
            
            # Approach 1: Look for Records in the main content area (the tab-like buttons)
            try:
                records_element = self.driver.find_element(By.XPATH, "//button[text()='Records' or contains(text(), 'Records')]")
                self.logger.info("Found Records button in main content area")
            except:
                pass
            
            # Approach 2: If that fails, try the sidebar Records link
            if not records_element:
                try:
                    records_element = self.driver.find_element(By.XPATH, "//nav//a[contains(text(), 'Records')] | //aside//a[contains(text(), 'Records')]")
                    self.logger.info("Found Records link in sidebar navigation")
                except:
                    pass
            
            # Approach 3: Try to be more specific - look for Records that are actually clickable
            if not records_element:
                try:
                    # Get all Records elements and try to find the clickable one
                    all_records = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Records')]")
                    self.logger.info(f"Found {len(all_records)} elements containing 'Records'")
                    
                    for i, elem in enumerate(all_records):
                        try:
                            # Check if this element is clickable
                            if elem.is_enabled() and elem.is_displayed():
                                tag = elem.tag_name
                                classes = elem.get_attribute('class')
                                self.logger.info(f"Records element {i+1}: tag={tag}, classes={classes}, text='{elem.text}'")
                                
                                # Prefer buttons over links, or elements in the main content
                                if tag == 'button' or 'button' in (classes or ''):
                                    records_element = elem
                                    self.logger.info(f"Selected Records button element {i+1}")
                                    break
                        except:
                            continue
                    
                    # If we didn't find a button, use the first clickable one
                    if not records_element:
                        for elem in all_records:
                            try:
                                if elem.is_enabled() and elem.is_displayed():
                                    records_element = elem
                                    self.logger.info("Selected first clickable Records element")
                                    break
                            except:
                                continue
                                
                except Exception as search_error:
                    self.logger.warning(f"Error searching for Records elements: {search_error}")
            
            # If we found the element, try to click it
            if records_element:
                try:
                    # Make sure it's visible
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", records_element)
                    time.sleep(1)
                    
                    # Try regular click first
                    records_element.click()
                    self.logger.info("Clicked Records element with regular click")
                    
                except Exception as click_error:
                    try:
                        # If regular click fails, try JavaScript click
                        self.driver.execute_script("arguments[0].click();", records_element)
                        self.logger.info("Clicked Records element using JavaScript")
                    except Exception as js_error:
                        self.logger.error(f"Both click methods failed: regular={click_error}, js={js_error}")
                        return False
                
                # Wait for records page/section to load
                time.sleep(5)
                
                # Check if we're now in the records section
                current_url = self.driver.current_url
                page_source_snippet = self.driver.page_source[:1000].lower()
                
                self.logger.info(f"After clicking Records - URL: {current_url}")
                
                if "records" in current_url.lower() or "records" in page_source_snippet:
                    self.logger.info("Successfully navigated to Records section")
                    return True
                else:
                    self.logger.warning(f"May have clicked Records but URL/content doesn't clearly indicate records section")
                    # Continue anyway - we might be in the right place
                    return True
            else:
                self.logger.error("Could not find any clickable Records element")
                return False
            
        except Exception as e:
            self.logger.error(f"Failed to navigate to Records: {str(e)}")
            return False
    
    def reset_form_if_needed(self):
        """Reset the form to ensure we have a clean slate for each file"""
        try:
            self.logger.info("Checking if form needs reset...")
            
            # Look for any existing content in form fields
            title_fields = self.driver.find_elements(By.XPATH, "//textarea[@placeholder='Title']")
            if title_fields:
                title_field = title_fields[0]
                current_title = title_field.get_attribute('value') or ''
                if current_title.strip():
                    self.logger.info(f"Form has existing title: '{current_title}', attempting to reset...")
                    
                    # Try to find and click a "Clear form" or "New record" button
                    clear_selectors = [
                        "//button[contains(text(), 'Clear form')]",
                        "//button[contains(text(), 'New')]",
                        "//button[contains(text(), 'Reset')]",
                        "//*[contains(text(), 'Clear')]"
                    ]
                    
                    for selector in clear_selectors:
                        try:
                            clear_button = self.driver.find_element(By.XPATH, selector)
                            if clear_button.is_displayed() and clear_button.is_enabled():
                                self.logger.info(f"Found clear button: {clear_button.text}")
                                clear_button.click()
                                time.sleep(3)
                                self.logger.info("Clicked clear button to reset form")
                                return True
                        except:
                            continue
                    
                    # If no clear button found, try to manually clear all fields
                    self.logger.info("No clear button found, manually clearing fields...")
                    self.clear_all_form_fields()
                    
                    # After manual clearing, check if fields are actually empty
                    time.sleep(1)
                    title_fields = self.driver.find_elements(By.XPATH, "//textarea[@placeholder='Title']")
                    if title_fields:
                        title_field = title_fields[0]
                        current_title = title_field.get_attribute('value') or ''
                        if current_title.strip():
                            self.logger.warning("Manual clearing didn't work, forcing form refresh...")
                            return self.force_form_refresh()
                    
            return True
            
        except Exception as e:
            self.logger.warning(f"Error in form reset: {e}")
            return True
    
    def clear_all_form_fields(self):
        """Manually clear all form fields to ensure clean state"""
        try:
            self.logger.info("Manually clearing all form fields...")
            
            # Clear title field
            title_fields = self.driver.find_elements(By.XPATH, "//textarea[@placeholder='Title']")
            if title_fields:
                title_field = title_fields[0]
                self.driver.execute_script("arguments[0].value = '';", title_field)
                time.sleep(0.5)
            
            # Clear original ID field
            id_fields = self.driver.find_elements(By.XPATH, "//input[@placeholder='Add ID…']")
            if id_fields:
                id_field = id_fields[0]
                self.driver.execute_script("arguments[0].value = '';", id_field)
                time.sleep(0.5)
            
            # Clear notes field
            notes_fields = self.driver.find_elements(By.XPATH, "//textarea[@placeholder='Add notes...']")
            if notes_fields:
                notes_field = notes_fields[0]
                self.driver.execute_script("arguments[0].value = '';", notes_field)
                time.sleep(0.5)
            
            # Clear date field
            date_fields = self.driver.find_elements(By.XPATH, "//input[@placeholder='Select date']")
            if date_fields:
                date_field = date_fields[0]
                self.driver.execute_script("arguments[0].value = '';", date_field)
                time.sleep(0.5)
            
            self.logger.info("All form fields cleared manually")
            
        except Exception as e:
            self.logger.warning(f"Error clearing form fields: {e}")
    
    def force_form_refresh(self):
        """Force a complete form refresh by going back to records and creating new record"""
        try:
            self.logger.info("Forcing complete form refresh...")
            
            # Navigate back to records page
            if not self.navigate_to_records():
                self.logger.warning("Could not navigate back to records page")
                return False
            
            # Click new record button again
            if not self.click_new_record_button():
                self.logger.warning("Could not click new record button after refresh")
                return False
            
            # Wait for form to load
            time.sleep(5)
            
            # Reset form again
            self.reset_form_if_needed()
            time.sleep(2)
            
            self.logger.info("Form refresh completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in form refresh: {e}")
            return False
    
    def click_new_record_button(self):
        """Click the + button to create a new record"""
        try:
            self.logger.info("Looking for + button to create new record...")
            
            # Wait for the records page to fully load
            time.sleep(3)
            
            plus_button = None
            
            # Approach 1: Look for the blue + button (it's likely a button with a + symbol)
            try:
                plus_button = self.driver.find_element(By.XPATH, "//button[contains(text(), '+')]")
                self.logger.info("Found + button with text")
            except:
                pass
            
            # Approach 2: Look for button with + symbol or add-related attributes
            if not plus_button:
                try:
                    plus_button = self.driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Add') or contains(@title, 'Add') or contains(@aria-label, 'New') or contains(@title, 'New')]")
                    self.logger.info("Found + button with add/new attributes")
                except:
                    pass
            
            # Approach 3: Look for any button in the top right area that might be the + button
            if not plus_button:
                try:
                    # Look for buttons that might be positioned in the header/top area
                    header_buttons = self.driver.find_elements(By.XPATH, "//header//button | //div[contains(@class, 'header')]//button | //*[contains(@class, 'top')]//button")
                    for btn in header_buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            btn_text = btn.text.strip()
                            btn_html = btn.get_attribute('outerHTML')
                            self.logger.info(f"Found header button: text='{btn_text}', html snippet='{btn_html[:100]}'")
                            
                            # Look for + or plus or add indicators
                            if '+' in btn_text or '+' in btn_html or 'plus' in btn_html.lower() or 'add' in btn_html.lower():
                                plus_button = btn
                                self.logger.info("Selected header button as + button")
                                break
                except Exception as e:
                    self.logger.warning(f"Error searching header buttons: {e}")
            
            # If we found a button, try to click it
            if plus_button:
                try:
                    # Make sure the button is visible
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", plus_button)
                    time.sleep(1)
                    
                    # Try regular click first
                    plus_button.click()
                    self.logger.info("Clicked + button with regular click")
                    
                except Exception as click_error:
                    try:
                        # Try JavaScript click as fallback
                        self.driver.execute_script("arguments[0].click();", plus_button)
                        self.logger.info("Clicked + button using JavaScript")
                    except Exception as js_error:
                        self.logger.error(f"Both click methods failed: regular={click_error}, js={js_error}")
                        return False
                
                # Wait for the new record form to load
                time.sleep(5)
                
                # Look for signs that the new record form opened
                try:
                    # Look for common form elements that might appear
                    form_indicators = [
                        "//input[@placeholder='Title']",
                        "//input[contains(@placeholder, 'title')]",
                        "//button[contains(text(), 'Save')]",
                        "//button[contains(text(), 'Create')]",
                        "//form",
                        "//*[contains(text(), 'New record')]",
                        "//*[contains(text(), 'Create record')]"
                    ]
                    
                    for indicator in form_indicators:
                        try:
                            element = self.driver.find_element(By.XPATH, indicator)
                            if element.is_displayed():
                                self.logger.info(f"Found new record form indicator: {indicator}")
                                return True
                        except:
                            continue
                    
                    # If no specific form indicators, check if URL changed or page content changed
                    current_url = self.driver.current_url
                    if "new" in current_url.lower() or "create" in current_url.lower():
                        self.logger.info("URL suggests new record form opened")
                        return True
                    
                    self.logger.warning("+ button was clicked but no clear form indicators found")
                    return True  # Continue anyway
                    
                except Exception as check_error:
                    self.logger.warning(f"Error checking for form: {check_error}")
                    return True  # Continue anyway
            else:
                self.logger.error("Could not find + button with any method")
                return False
            
        except Exception as e:
            self.logger.error(f"Failed to click new record button: {str(e)}")
            return False
    
    def debug_form_fields(self):
        """Debug function to analyze the form structure"""
        try:
            self.logger.info("=== DEBUGGING FORM STRUCTURE ===")
            
            # Take a screenshot
            self.driver.save_screenshot("debug_form_structure.png")
            self.logger.info("Screenshot saved as debug_form_structure.png")
            
            # List all input fields with their properties
            all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
            self.logger.info(f"Found {len(all_inputs)} input fields:")
            
            for i, inp in enumerate(all_inputs):
                try:
                    if inp.is_displayed():
                        input_type = inp.get_attribute('type') or 'text'
                        placeholder = inp.get_attribute('placeholder') or ''
                        value = inp.get_attribute('value') or ''
                        name = inp.get_attribute('name') or ''
                        id_attr = inp.get_attribute('id') or ''
                        classes = inp.get_attribute('class') or ''
                        
                        self.logger.info(f"  Input {i+1}: type={input_type}, placeholder='{placeholder}', "
                                       f"value='{value}', name='{name}', id='{id_attr}', classes='{classes[:50]}...'")
                except Exception as e:
                    self.logger.warning(f"  Input {i+1}: Error reading properties: {e}")
            
            # List all labels
            all_labels = self.driver.find_elements(By.TAG_NAME, "label")
            self.logger.info(f"Found {len(all_labels)} labels:")
            for i, label in enumerate(all_labels):
                try:
                    if label.is_displayed():
                        text = label.text.strip()
                        for_attr = label.get_attribute('for') or ''
                        self.logger.info(f"  Label {i+1}: text='{text}', for='{for_attr}'")
                except:
                    pass
            
            # List all textareas
            all_textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
            self.logger.info(f"Found {len(all_textareas)} textarea fields:")
            for i, ta in enumerate(all_textareas):
                try:
                    if ta.is_displayed():
                        placeholder = ta.get_attribute('placeholder') or ''
                        name = ta.get_attribute('name') or ''
                        self.logger.info(f"  Textarea {i+1}: placeholder='{placeholder}', name='{name}'")
                except:
                    pass
            
            # List all buttons
            all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
            self.logger.info(f"Found {len(all_buttons)} buttons:")
            for i, btn in enumerate(all_buttons):
                try:
                    if btn.is_displayed():
                        text = btn.text.strip()
                        classes = btn.get_attribute('class') or ''
                        self.logger.info(f"  Button {i+1}: text='{text}', classes='{classes[:50]}...'")
                except:
                    pass
            
            self.logger.info("=== END FORM DEBUGGING ===")
            
        except Exception as e:
            self.logger.error(f"Error in debug_form_fields: {e}")
    
    def upload_file_to_archive_ox(self, file_path, source_info="", record_type="Footage", project_name="", copyright_owner="", date_value="", notes=""):
        """Create a record in Archive Ox using the filename (NO file upload) - COMPLETELY FIXED VERSION"""
        try:
            # Select the project if specified
            if project_name and not self.select_project(project_name):
                return None
            
            # Navigate to Records section
            if not self.navigate_to_records():
                return None
                
            # Click the + button to create new record
            if not self.click_new_record_button():
                return None
            
            self.logger.info(f"Filling out record form for: {file_path}")
            
            # Wait for form to be fully loaded
            time.sleep(5)
            
            # Reset form if needed to ensure clean state for each file
            self.reset_form_if_needed()
            time.sleep(2)
            
            # Debug the form structure (you can comment this out later)
            self.debug_form_fields()
            
            # First, check for and dismiss any overlays/modals that might be blocking interaction
            try:
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(2)
                self.logger.info("Pressed Escape to dismiss any overlays")
            except:
                pass
            
            # 1. Fill in the Title field - IT'S A TEXTAREA, NOT AN INPUT!
            try:
                self.logger.info("Looking for title TEXTAREA field...")
                
                # Get just the filename without extension
                filename_only = Path(file_path).stem  # This gets "H205" from "H205.MP4"
                self.logger.info(f"Target filename for title: '{filename_only}'")
                
                # Always get fresh element references to avoid stale element issues
                title_field = None
                
                # Strategy 1: Look for textarea with placeholder="Title"
                try:
                    title_field = self.driver.find_element(By.XPATH, "//textarea[@placeholder='Title']")
                    if title_field.is_displayed() and title_field.is_enabled():
                        self.logger.info("Found title field: textarea with placeholder='Title'")
                    else:
                        title_field = None
                except Exception as e:
                    self.logger.warning(f"Could not find textarea with placeholder='Title': {e}")
                
                # Strategy 2: Look for any textarea (there should only be one for title based on debug output)
                if not title_field:
                    try:
                        textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
                        for i, ta in enumerate(textareas):
                            if ta.is_displayed() and ta.is_enabled():
                                placeholder = ta.get_attribute('placeholder') or ""
                                name = ta.get_attribute('name') or ""
                                self.logger.info(f"Textarea {i+1}: placeholder='{placeholder}', name='{name}'")
                                
                                # If it has "Title" placeholder, that's our field
                                if 'title' in placeholder.lower():
                                    title_field = ta
                                    self.logger.info(f"Selected textarea {i+1} as title field")
                                    break
                        
                        # If no title placeholder found, use the first textarea
                        if not title_field and textareas:
                            title_field = textareas[0]
                            self.logger.info("Using first textarea as title field")
                            
                    except Exception as e:
                        self.logger.warning(f"Error searching textareas: {e}")
                
                # Fill the title field if found
                if title_field:
                    try:
                        # Scroll to make sure the field is visible
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", title_field)
                        time.sleep(1)
                        
                        # AGGRESSIVE CLEARING: Multiple methods to ensure field is completely empty
                        # Method 1: Selenium clear
                        title_field.clear()
                        time.sleep(0.5)
                        
                        # Method 2: JavaScript clear
                        self.driver.execute_script("arguments[0].value = '';", title_field)
                        time.sleep(0.5)
                        
                        # Method 3: Select all and delete
                        title_field.send_keys(Keys.CONTROL + "a")
                        title_field.send_keys(Keys.DELETE)
                        time.sleep(0.5)
                        
                        # Method 4: JavaScript select all and clear
                        self.driver.execute_script("""
                            var element = arguments[0];
                            element.select();
                            element.value = '';
                        """, title_field)
                        time.sleep(0.5)
                        
                        # Verify field is actually empty before entering new text
                        current_value = title_field.get_attribute('value')
                        if current_value and current_value.strip():
                            self.logger.warning(f"Title field still has content after clearing: '{current_value}'")
                            # Force clear one more time
                            self.driver.execute_script("arguments[0].value = '';", title_field)
                            time.sleep(0.5)
                        else:
                            self.logger.info("Title field is now empty and ready for new content")
                        
                        # Enter ONLY the filename without extension
                        title_field.send_keys(filename_only)
                        
                        # Trigger events to make sure the form recognizes the input
                        self.driver.execute_script("""
                            var element = arguments[0];
                            var inputEvent = new Event('input', { bubbles: true });
                            var changeEvent = new Event('change', { bubbles: true });
                            element.dispatchEvent(inputEvent);
                            element.dispatchEvent(changeEvent);
                        """, title_field)
                        
                        # Verify the text was entered correctly
                        entered_value = title_field.get_attribute('value')
                        if entered_value == filename_only:
                            self.logger.info(f"Successfully entered title: '{filename_only}'")
                        else:
                            self.logger.warning(f"Title field shows '{entered_value}' but expected '{filename_only}'")
                            # Try to fix it with one more aggressive clear and set
                            self.driver.execute_script("arguments[0].value = '';", title_field)
                            time.sleep(0.5)
                            title_field.send_keys(filename_only)
                            self.logger.info(f"Fixed title field to: '{filename_only}'")
                            
                    except Exception as interaction_error:
                        self.logger.error(f"Could not interact with title field: {interaction_error}")
                        return None
                else:
                    self.logger.error("Could not find title textarea field")
                    return None
                    
            except Exception as e:
                self.logger.error(f"Could not fill title field: {str(e)}")
                return None
            
            # 2. Set record type (Audio, Footage, Still) - Use label-based selection
            try:
                self.logger.info(f"Setting record type to: {record_type}")
                
                # From the debug output, we know the labels exist: 'Audio', 'Footage', 'Still'
                # Let's find the label and click it or its associated element
                record_type_element = None
                
                # Strategy 1: Look for the label and find its associated button/input
                try:
                    # Find the label with the record type text
                    label = self.driver.find_element(By.XPATH, f"//label[text()='{record_type}']")
                    if label.is_displayed():
                        # Get the 'for' attribute to find the associated element
                        for_attr = label.get_attribute('for')
                        self.logger.info(f"Found {record_type} label with for='{for_attr}'")
                        
                        if for_attr:
                            # Try to find the element with this ID
                            try:
                                record_type_element = self.driver.find_element(By.ID, for_attr)
                                self.logger.info(f"Found {record_type} button/input by ID")
                            except:
                                # If ID doesn't work, click the label itself
                                record_type_element = label
                                self.logger.info(f"Will click {record_type} label directly")
                        else:
                            # No 'for' attribute, click the label itself
                            record_type_element = label
                            self.logger.info(f"Will click {record_type} label directly (no for attribute)")
                            
                except Exception as e:
                    self.logger.warning(f"Could not find {record_type} label: {e}")
                
                # Strategy 2: Look for button containing the record type text
                if not record_type_element:
                    try:
                        buttons = self.driver.find_elements(By.XPATH, f"//button[contains(text(), '{record_type}')]")
                        for btn in buttons:
                            if btn.is_displayed() and btn.is_enabled():
                                record_type_element = btn
                                self.logger.info(f"Found {record_type} button")
                                break
                    except Exception as e:
                        self.logger.warning(f"Could not find {record_type} button: {e}")
                
                # Click the record type element
                if record_type_element:
                    try:
                        self.driver.execute_script("arguments[0].click();", record_type_element)
                        self.logger.info(f"Selected record type: {record_type}")
                        time.sleep(1)
                    except Exception as e:
                        self.logger.warning(f"Could not click {record_type} element: {e}")
                else:
                    self.logger.warning(f"Could not find any {record_type} element to click")
                    
            except Exception as e:
                self.logger.warning(f"Could not set record type: {str(e)}")
            
            # 3. Fill Original ID field
            try:
                self.logger.info("Looking for Original ID field...")
                
                original_id_field = None
                original_filename = Path(file_path).name  # Include extension for Original ID
                
                # From debug output: Input 7: placeholder='Add ID…', name='ceabezyhdj', id='ceabezyhdj'
                # Look for Original ID field using various methods
                selectors = [
                    "//input[@placeholder='Add ID…']",  # Exact match from debug
                    "//input[@placeholder='Add ID...']",  # In case of different ellipsis
                    "//input[contains(@placeholder, 'Add ID')]",  # Partial match
                    "//*[text()='Original ID']/following::input[1]",  # Based on label
                    "//label[text()='Original ID']//following::input[1]",  # Alternative label approach
                ]
                
                for selector in selectors:
                    try:
                        original_id_field = self.driver.find_element(By.XPATH, selector)
                        if original_id_field.is_displayed() and original_id_field.is_enabled():
                            self.logger.info(f"Found Original ID field with selector: {selector}")
                            break
                    except:
                        continue
                
                if original_id_field:
                    # AGGRESSIVE CLEARING: Multiple methods to ensure field is completely empty
                    # Method 1: Selenium clear
                    original_id_field.clear()
                    time.sleep(0.5)
                    
                    # Method 2: JavaScript clear
                    self.driver.execute_script("arguments[0].value = '';", original_id_field)
                    time.sleep(0.5)
                    
                    # Method 3: Select all and delete
                    original_id_field.send_keys(Keys.CONTROL + "a")
                    original_id_field.send_keys(Keys.DELETE)
                    time.sleep(0.5)
                    
                    # Method 4: JavaScript select all and clear
                    self.driver.execute_script("""
                        var element = arguments[0];
                        element.select();
                        element.value = '';
                    """, original_id_field)
                    time.sleep(0.5)
                    
                    # Verify field is actually empty before entering new text
                    current_value = original_id_field.get_attribute('value')
                    if current_value and current_value.strip():
                        self.logger.warning(f"Original ID field still has content after clearing: '{current_value}'")
                        # Force clear one more time
                        self.driver.execute_script("arguments[0].value = '';", original_id_field)
                        time.sleep(0.5)
                    else:
                        self.logger.info("Original ID field is now empty and ready for new content")
                    
                    # Enter the filename with extension
                    original_id_field.send_keys(original_filename)
                    self.logger.info(f"Set Original ID: {original_filename}")
                else:
                    self.logger.warning("Could not find Original ID field")
                    
            except Exception as e:
                self.logger.warning(f"Could not set Original ID: {str(e)}")
            
            # 4. Set date if provided
            if date_value:
                try:
                    self.logger.info(f"Setting date: {date_value}")
                    
                    # Look for date field - from debug: placeholder='Select date'
                    date_selectors = [
                        "//input[@placeholder='Select date']",
                        "//input[contains(@placeholder, 'date')]",
                        "//button[contains(text(), 'Select date')]",
                        "//*[text()='Date']/following::input[1]"
                    ]
                    
                    date_element = None
                    for selector in date_selectors:
                        try:
                            date_element = self.driver.find_element(By.XPATH, selector)
                            if date_element.is_displayed() and date_element.is_enabled():
                                self.logger.info(f"Found date field with selector: {selector}")
                                break
                        except:
                            continue
                    
                    if date_element:
                        # For date pickers, we need to be more careful about the format
                        self.logger.info(f"Date field found, attempting to set date: {date_value}")
                        
                        # Clear the field first
                        date_element.clear()
                        time.sleep(1)
                        
                        # Try multiple approaches for date entry
                        try:
                            # Approach 1: Direct JavaScript injection (bypasses date picker validation)
                            self.driver.execute_script("arguments[0].value = arguments[1];", date_element, date_value)
                            time.sleep(1)
                            
                            # Approach 2: If that didn't work, try typing with proper format
                            current_value = date_element.get_attribute('value')
                            if not current_value or current_value != date_value:
                                self.logger.info("JavaScript injection didn't work, trying typing approach...")
                                
                                # Clear again and try typing
                                date_element.clear()
                                time.sleep(0.5)
                                
                                # Click to focus the field first
                                date_element.click()
                                time.sleep(0.5)
                                
                                # Type the date
                                date_element.send_keys(date_value)
                                time.sleep(1)
                            
                            # Approach 3: Force the value and trigger events
                            self.driver.execute_script("""
                                var element = arguments[0];
                                var dateValue = arguments[1];
                                
                                // Set the value directly
                                element.value = dateValue;
                                
                                // Trigger all necessary events
                                element.dispatchEvent(new Event('input', { bubbles: true }));
                                element.dispatchEvent(new Event('change', { bubbles: true }));
                                element.dispatchEvent(new Event('blur', { bubbles: true }));
                                
                                // Also try setting the attribute
                                element.setAttribute('value', dateValue);
                            """, date_element, date_value)
                            time.sleep(1)
                            
                            # Final verification
                            final_date = date_element.get_attribute('value')
                            if final_date:
                                self.logger.info(f"✅ Date field now contains: '{final_date}'")
                            else:
                                self.logger.warning("Date field is still empty after all attempts")
                                
                        except Exception as date_error:
                            self.logger.warning(f"Error setting date: {date_error}")
                        
                        # CRITICAL: After setting the date, prevent it from being cleared
                        # by monitoring and re-applying if it gets cleared
                        self.logger.info("Setting up date field monitoring to prevent clearing...")
                        self.driver.execute_script("""
                            var element = arguments[0];
                            var targetDate = arguments[1];
                            
                            // Store the target date in the element's data
                            element.dataset.targetDate = targetDate;
                            
                            // Create a mutation observer to watch for value changes
                            var observer = new MutationObserver(function(mutations) {
                                mutations.forEach(function(mutation) {
                                    if (mutation.type === 'attributes' && mutation.attributeName === 'value') {
                                        var currentValue = element.value;
                                        if (!currentValue || currentValue === '') {
                                            console.log('Date field was cleared, restoring value...');
                                            element.value = targetDate;
                                            element.dispatchEvent(new Event('input', { bubbles: true }));
                                            element.dispatchEvent(new Event('change', { bubbles: true }));
                                        }
                                    }
                                });
                            });
                            
                            // Start observing
                            observer.observe(element, { attributes: true, attributeFilter: ['value'] });
                            
                            // Also set up a periodic check as backup
                            setInterval(function() {
                                if (!element.value || element.value === '') {
                                    console.log('Date field empty, restoring value...');
                                    element.value = targetDate;
                                    element.dispatchEvent(new Event('input', { bubbles: true }));
                                    element.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            }, 1000);
                        """, date_element, date_value)
                            
                    else:
                        self.logger.warning("Could not find date field")
                        
                except Exception as e:
                    self.logger.warning(f"Could not set date: {str(e)}")
            
            # 5. Set copyright if provided (non-blocking)
            if copyright_owner:
                try:
                    self.logger.info(f"Setting copyright to: {copyright_owner}")
                    
                    # Look for the Copyright dropdown field using the correct HTML structure
                    copyright_selectors = [
                        # Target the Copyright field specifically by looking for the label first
                        "//label[text()='Copyright']/following::div[contains(@class, 'ox-select')][1]//div[contains(@class, 'cursor-pointer')]",
                        "//label[text()='Copyright*']/following::div[contains(@class, 'ox-select')][1]//div[contains(@class, 'cursor-pointer')]",
                        # Fallback: look for Copyright field by its position in the form
                        "(//div[contains(@class, 'ox-select') and contains(@class, 'ox-select--single')])[2]//div[contains(@class, 'cursor-pointer')]",
                        # Last resort: any ox-select with cursor-pointer
                        "//div[contains(@class, 'ox-select')]//div[contains(@class, 'cursor-pointer')]"
                    ]
                    
                    copyright_field = None
                    for i, selector in enumerate(copyright_selectors):
                        try:
                            copyright_field = self.driver.find_element(By.XPATH, selector)
                            if copyright_field.is_displayed():
                                self.logger.info(f"Found copyright field with selector #{i+1}: {selector}")
                                break
                        except Exception as e:
                            self.logger.info(f"Selector #{i+1} failed: {e}")
                            continue
                    
                    if copyright_field:
                        try:
                            # Click the copyright field to open the dropdown
                            self.logger.info("Clicking copyright field to open dropdown...")
                            copyright_field.click()
                            time.sleep(2)  # Wait for dropdown to open
                            
                            # Look for the search input that appears in the dropdown
                            search_input = None
                            search_selectors = [
                                "//div[contains(@class, 'tag-autocomplete-dropdown')]//input[@placeholder='Search']",
                                "//div[contains(@class, 'tag-autocomplete-dropdown')]//input[contains(@placeholder, 'Search')]",
                                "//div[contains(@class, 'dropdown')]//input[contains(@placeholder, 'Search')]",
                                "//div[contains(@class, 'z-86')]//input[contains(@placeholder, 'Search')]"
                            ]
                            
                            for search_selector in search_selectors:
                                try:
                                    search_input = self.driver.find_element(By.XPATH, search_selector)
                                    if search_input.is_displayed() and search_input.is_enabled():
                                        self.logger.info(f"Found search input with selector: {search_selector}")
                                        break
                                except:
                                    continue
                            
                            if search_input:
                                # Clear and type the search term
                                self.logger.info(f"Typing search term: '{copyright_owner}'")
                                try:
                                    search_input.clear()
                                    time.sleep(0.5)
                                    search_input.send_keys(copyright_owner)
                                    time.sleep(1)
                                    self.logger.info(f"Successfully typed '{copyright_owner}' into search input")
                                except Exception as type_error:
                                    self.logger.warning(f"Error typing into search input: {type_error}")
                                    # Try alternative method - click and type
                                    try:
                                        search_input.click()
                                        time.sleep(0.5)
                                        search_input.send_keys(Keys.CONTROL + "a")  # Select all
                                        search_input.send_keys(Keys.DELETE)         # Delete
                                        time.sleep(0.5)
                                        search_input.send_keys(copyright_owner)
                                        time.sleep(1)
                                        self.logger.info(f"Successfully typed '{copyright_owner}' using alternative method")
                                    except Exception as alt_error:
                                        self.logger.warning(f"Alternative typing method also failed: {alt_error}")
                                
                                # Look for the matching option in the dropdown
                                option_selectors = [
                                    f"//div[contains(@class, 'tag-autocomplete-dropdown')]//*[contains(text(), '{copyright_owner}')]",
                                    f"//div[contains(@class, 'z-86')]//*[contains(text(), '{copyright_owner}')]",
                                    f"//div[contains(@class, 'dropdown')]//*[contains(text(), '{copyright_owner}')]",
                                    f"//div[contains(@class, 'cursor-pointer')]//*[contains(text(), '{copyright_owner}')]"
                                ]
                                
                                copyright_option = None
                                for option_selector in option_selectors:
                                    try:
                                        copyright_option = self.driver.find_element(By.XPATH, option_selector)
                                        if copyright_option.is_displayed() and copyright_option.is_enabled():
                                            self.logger.info(f"Found copyright option with selector: {option_selector}")
                                            break
                                    except:
                                        continue
                                
                                if copyright_option:
                                    # Click the option to select it
                                    self.logger.info(f"Clicking copyright option: {copyright_owner}")
                                    copyright_option.click()
                                    time.sleep(1)
                                    
                                    # Verify the selection was made
                                    try:
                                        # Check if the copyright field now shows the selected value
                                        field_text = copyright_field.text or copyright_field.get_attribute('value') or copyright_field.get_attribute('innerText')
                                        if copyright_owner in field_text:
                                            self.logger.info(f"✅ Copyright successfully set to: {copyright_owner}")
                                        else:
                                            self.logger.warning(f"Copyright verification failed. Field shows: '{field_text}'")
                                    except Exception as verify_error:
                                        self.logger.warning(f"Could not verify copyright selection: {verify_error}")
                                else:
                                    self.logger.warning(f"Could not find copyright option for: {copyright_owner}")
                            else:
                                self.logger.warning("Could not find search input in copyright dropdown")
                        except Exception as copyright_error:
                            self.logger.warning(f"Error setting copyright: {copyright_error}")
                    else:
                        self.logger.warning("Could not find copyright field")
                        
                except Exception as e:
                    self.logger.warning(f"Could not set copyright: {str(e)}")
                    # Continue with the process - don't let copyright failure block notes
            
            # Small delay after copyright to ensure form stability (regardless of success/failure)
            time.sleep(1)
                    
            # 6. Add notes - IMMEDIATELY after copyright to prevent field from disappearing
            try:
                self.logger.info(f"=== NOTES DEBUG ===")
                self.logger.info(f"Custom notes from GUI: '{notes}'")
                self.logger.info(f"Source info: '{source_info}'")
                self.logger.info(f"File path: '{file_path}'")
                
                notes_content = []
                
                # Add custom notes from GUI if provided
                if notes and notes.strip():
                    notes_content.append(notes.strip())
                    self.logger.info(f"Added custom notes: '{notes.strip()}'")
                else:
                    self.logger.info("No custom notes provided")
                
                # Add source info if provided
                if source_info:
                    notes_content.append(f"Source: {source_info}")
                    self.logger.info(f"Added source info: 'Source: {source_info}'")
                else:
                    self.logger.info("No source info provided")
                
                # Always add the file path for this specific clip
                notes_content.append(f"Local file: {file_path}")
                self.logger.info(f"Added file path: 'Local file: {file_path}'")
                
                self.logger.info(f"Final notes content: {notes_content}")
                
                if notes_content:
                    # SIMPLIFIED NOTES APPROACH: Find and fill notes field immediately
                    self.logger.info("Searching for notes field with simplified approach...")
                    
                    notes_field = None
                    notes_text = "\n".join(notes_content)
                    
                    # No delay needed since copyright is disabled
                    
                    notes_selectors = [
                        "//*[@data-test='ox-record-notes-field']",
                        "//textarea[@placeholder='Add notes...']",
                        "//textarea[contains(@placeholder, 'notes')]",
                        "//textarea[contains(@placeholder, 'Notes')]",
                        "//*[text()='Notes']/following::textarea[1]",
                        "//label[text()='Notes']/following::textarea[1]"
                    ]
                    
                    for selector in notes_selectors:
                        try:
                            notes_field = self.driver.find_element(By.XPATH, selector)
                            if notes_field.is_displayed():
                                # Log what we found
                                placeholder = notes_field.get_attribute('placeholder') or ""
                                name = notes_field.get_attribute('name') or ""
                                data_test = notes_field.get_attribute('data-test') or ""
                                tag_name = notes_field.tag_name
                                
                                self.logger.info(f"Found element with selector: {selector}")
                                self.logger.info(f"  Tag: {tag_name}, Placeholder: '{placeholder}', Name: '{name}', Data-test: '{data_test}'")
                                
                                # Make sure this isn't the title textarea
                                if 'title' not in placeholder.lower() and 'title' not in name.lower():
                                    self.logger.info(f"✅ Using this as notes field")
                                    break
                                else:
                                    self.logger.info(f"❌ Skipping - appears to be title field")
                                    notes_field = None
                        except Exception as e:
                            self.logger.info(f"Selector '{selector}' failed: {e}")
                            continue
                    
                    # If no specific notes field found, look for second textarea (first is title)
                    if not notes_field:
                        try:
                            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
                            self.logger.info(f"Found {len(textareas)} total textareas")
                            
                            for i, ta in enumerate(textareas):
                                if ta.is_displayed():
                                    placeholder = ta.get_attribute('placeholder') or ""
                                    name = ta.get_attribute('name') or ""
                                    self.logger.info(f"Textarea {i+1}: placeholder='{placeholder}', name='{name}'")
                                    
                                    # Skip the title textarea
                                    if 'title' not in placeholder.lower():
                                        notes_field = ta
                                        self.logger.info(f"Using textarea {i+1} as notes field")
                                        break
                        except Exception as e:
                            self.logger.warning(f"Error finding textareas: {e}")
                    
                    if notes_field:
                        try:
                            self.logger.info(f"Found notes field, entering notes immediately: '{notes_text}'")
                            self.logger.info(f"Notes field details: tag={notes_field.tag_name}, type={notes_field.get_attribute('type')}, class={notes_field.get_attribute('class')}")
                            
                            # For rich text editors (CKEditor), we need to use the proper API
                            if 'field-editor' in (notes_field.get_attribute('class') or ''):
                                self.logger.info("Notes field is a rich text editor - using CKEditor API method")
                                
                                # Method 1: Try to find and use the CKEditor instance
                                try:
                                    # Look for CKEditor instance in the page
                                    ckeditor_instance = self.driver.execute_script("""
                                        // Try to find CKEditor instance
                                        if (window.CKEDITOR && window.CKEDITOR.instances) {
                                            for (var name in window.CKEDITOR.instances) {
                                                if (window.CKEDITOR.instances[name].element && 
                                                    window.CKEDITOR.instances[name].element.$ === arguments[0]) {
                                                    return window.CKEDITOR.instances[name];
                                                }
                                            }
                                        }
                                        return null;
                                    """, notes_field)
                                    
                                    if ckeditor_instance:
                                        self.logger.info("Found CKEditor instance, using setData method")
                                        self.driver.execute_script("""
                                            arguments[0].setData(arguments[1]);
                                        """, ckeditor_instance, notes_text)
                                        time.sleep(1)
                                    else:
                                        self.logger.info("No CKEditor instance found, trying alternative method")
                                        # Method 2: Try to activate the rich text editor first
                                        self.logger.info("Attempting to activate rich text editor...")
                                        
                                        # First, try to find and click the actual editable area within the editor
                                        try:
                                            # Look for the actual editable content area
                                            editable_area = self.driver.find_element(By.XPATH, "//*[@data-test='ox-record-notes-field']//div[@contenteditable='true'] | //*[@data-test='ox-record-notes-field']//iframe | //*[@data-test='ox-record-notes-field']//textarea")
                                            if editable_area:
                                                self.logger.info("Found editable area within notes field")
                                                editable_area.click()
                                                time.sleep(1)
                                                
                                                # Now try to type into the editable area
                                                editable_area.send_keys(Keys.CONTROL + "a")
                                                time.sleep(0.5)
                                                editable_area.send_keys(Keys.DELETE)
                                                time.sleep(1)
                                                
                                                # Type the notes
                                                editable_area.send_keys(notes_text)
                                                time.sleep(1)
                                                self.logger.info("Successfully typed notes into editable area")
                                            else:
                                                self.logger.info("No editable area found, trying to activate the main field")
                                                # Try to activate the main field by clicking and waiting
                                                notes_field.click()
                                                time.sleep(2)  # Wait longer for editor to activate
                                                
                                                # Now try the original approach
                                                notes_field.send_keys(Keys.CONTROL + "a")
                                                time.sleep(0.5)
                                                notes_field.send_keys(Keys.DELETE)
                                                time.sleep(1)
                                                
                                                # Type the notes character by character
                                                for char in notes_text:
                                                    notes_field.send_keys(char)
                                                    time.sleep(0.01)
                                                
                                                time.sleep(1)
                                                self.logger.info("Finished typing notes into main field")
                                                
                                        except Exception as editable_error:
                                            self.logger.warning(f"Editable area approach failed: {editable_error}")
                                            # Fallback to the original method
                                            self.logger.info("Using fallback typing method for notes...")
                                            notes_field.click()
                                            time.sleep(1)
                                            notes_field.send_keys(Keys.CONTROL + "a")
                                            time.sleep(1)
                                            notes_field.send_keys(Keys.DELETE)
                                            time.sleep(1)
                                            
                                            # Type character by character for better recognition
                                            for char in notes_text:
                                                notes_field.send_keys(char)
                                                time.sleep(0.01)
                                            
                                            time.sleep(1)
                                            self.logger.info("Finished fallback notes entry")
                                        
                                except Exception as ck_error:
                                    self.logger.warning(f"CKEditor method failed: {ck_error}")
                                    # Fallback to basic method
                                    self.logger.info("Using fallback typing method for notes...")
                                    notes_field.click()
                                    time.sleep(1)
                                    notes_field.send_keys(Keys.CONTROL + "a")
                                    notes_field.send_keys(Keys.DELETE)
                                    time.sleep(1)
                                    
                                    # Type character by character for better recognition
                                    for char in notes_text:
                                        notes_field.send_keys(char)
                                        time.sleep(0.01)
                                    
                                    time.sleep(1)
                                    self.logger.info("Finished fallback notes entry")
                                
                                # Trigger proper change events for rich text editor
                                self.logger.info("Triggering proper change events for rich text editor...")
                                self.driver.execute_script("""
                                    var element = arguments[0];
                                    // Trigger focus and blur events
                                    element.focus();
                                    element.blur();
                                    // Trigger input and change events
                                    var inputEvent = new Event('input', { bubbles: true });
                                    var changeEvent = new Event('change', { bubbles: true });
                                    element.dispatchEvent(inputEvent);
                                    element.dispatchEvent(changeEvent);
                                """, notes_field)
                                time.sleep(2)  # Give editor time to process
                                
                                # Final verification - check if notes are actually in the editor
                                try:
                                    # Try to get content from the editor
                                    editor_content = self.driver.execute_script("""
                                        var element = arguments[0];
                                        // Try multiple ways to get content
                                        if (element.textContent) return element.textContent;
                                        if (element.innerText) return element.innerText;
                                        if (element.innerHTML) return element.innerHTML;
                                        return '';
                                    """, notes_field)
                                    
                                    if editor_content and notes_text.strip() in editor_content:
                                        self.logger.info(f"✅ Notes verification: Editor contains our notes!")
                                        self.logger.info(f"Editor content preview: '{editor_content[:100]}...'")
                                    else:
                                        self.logger.warning(f"❌ Notes verification failed: Editor content doesn't match expected notes")
                                        self.logger.info(f"Expected: '{notes_text[:100]}...'")
                                        self.logger.info(f"Got: '{editor_content[:100]}...'")
                                        
                                        # FINAL ATTEMPT: Try to force the content using JavaScript
                                        self.logger.info("Attempting final JavaScript injection for notes...")
                                        try:
                                            # Try to set content directly in multiple ways
                                            self.driver.execute_script("""
                                                var element = arguments[0];
                                                var content = arguments[1];
                                                
                                                // Method 1: Set innerHTML
                                                if (element.innerHTML !== undefined) {
                                                    element.innerHTML = content;
                                                }
                                                
                                                // Method 2: Set textContent
                                                if (element.textContent !== undefined) {
                                                    element.textContent = content;
                                                }
                                                
                                                // Method 3: Set innerText
                                                if (element.innerText !== undefined) {
                                                    element.innerText = content;
                                                }
                                                
                                                // Trigger events
                                                element.dispatchEvent(new Event('input', { bubbles: true }));
                                                element.dispatchEvent(new Event('change', { bubbles: true }));
                                            """, notes_field, notes_text)
                                            time.sleep(1)
                                            
                                            # Check if it worked
                                            final_content = self.driver.execute_script("""
                                                var element = arguments[0];
                                                return element.textContent || element.innerText || element.innerHTML || '';
                                            """, notes_field)
                                            
                                            if final_content and notes_text.strip() in final_content:
                                                self.logger.info("✅ Final JavaScript injection successful!")
                                            else:
                                                self.logger.warning("❌ Final JavaScript injection also failed")
                                                
                                        except Exception as final_error:
                                            self.logger.warning(f"Final JavaScript injection failed: {final_error}")
                                            
                                except Exception as verify_error:
                                    self.logger.warning(f"Could not verify notes content: {verify_error}")
                                
                            # For contenteditable divs (rich text editors), we need to use innerHTML, not value
                            elif notes_field.get_attribute('contenteditable') == 'true':
                                self.logger.info("Notes field is contenteditable - using innerHTML method")
                                
                                # Clear the field first
                                self.driver.execute_script("arguments[0].innerHTML = '';", notes_field)
                                time.sleep(0.5)
                                
                                # Set content using innerHTML
                                self.driver.execute_script("arguments[0].innerHTML = arguments[1];", notes_field, notes_text)
                                time.sleep(1)
                                
                                # Trigger change events to make CKEditor recognize the content
                                self.logger.info("Triggering change events for CKEditor...")
                                self.driver.execute_script("""
                                    var element = arguments[0];
                                    var event = new Event('input', { bubbles: true });
                                    element.dispatchEvent(event);
                                    var changeEvent = new Event('change', { bubbles: true });
                                    element.dispatchEvent(changeEvent);
                                """, notes_field)
                                time.sleep(1)
                                
                                # Verify using innerHTML
                                entered_notes = notes_field.get_attribute('innerHTML')
                                self.logger.info(f"After innerHTML injection, field innerHTML: '{entered_notes}'")
                                
                                if entered_notes == notes_text:
                                    self.logger.info("✅ Notes successfully entered via innerHTML!")
                                else:
                                    self.logger.warning(f"innerHTML verification failed. Expected: '{notes_text}', Got: '{entered_notes}'")
                                    # Try alternative method for rich text editors
                                    self.logger.info("Trying alternative method for rich text editor...")
                                    self.driver.execute_script("arguments[0].textContent = arguments[1];", notes_field, notes_text)
                                    time.sleep(1)
                                    entered_notes = notes_field.get_attribute('textContent')
                                    self.logger.info(f"After textContent injection: '{entered_notes}'")
                                    
                            else:
                                # Fallback for regular input fields
                                self.logger.info("Notes field is not a rich text editor - using value method")
                                
                                # Try to clear first
                                try:
                                    notes_field.clear()
                                    self.logger.info("Cleared notes field")
                                except Exception as clear_error:
                                    self.logger.warning(f"Could not clear field: {clear_error}")
                                
                                # Direct JavaScript injection
                                self.driver.execute_script("arguments[0].value = arguments[1];", notes_field, notes_text)
                                time.sleep(1)
                                
                                # Verify notes were entered
                                entered_notes = notes_field.get_attribute('value')
                                self.logger.info(f"After JavaScript injection, field value: '{entered_notes}'")
                                
                                if entered_notes == notes_text:
                                    self.logger.info("✅ Notes successfully entered!")
                                else:
                                    self.logger.warning(f"Notes verification failed. Expected: '{notes_text}', Got: '{entered_notes}'")
                                
                        except Exception as e:
                            self.logger.error(f"Failed to enter notes: {e}")
                            import traceback
                            self.logger.error(f"Full traceback: {traceback.format_exc()}")
                    else:
                        self.logger.error("❌ Could not find notes field!")
                        # List all available textareas for debugging
                        try:
                            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
                            self.logger.info(f"Available textareas ({len(textareas)}):")
                            for i, ta in enumerate(textareas):
                                if ta.is_displayed():
                                    placeholder = ta.get_attribute('placeholder') or ""
                                    name = ta.get_attribute('name') or ""
                                    self.logger.info(f"  Textarea {i+1}: placeholder='{placeholder}', name='{name}'")
                        except Exception as e:
                            self.logger.warning(f"Error listing textareas: {e}")
                        
            except Exception as e:
                self.logger.warning(f"Could not set notes: {str(e)}")
            
            # 6.4. Verify date was entered before saving
            if date_value:
                try:
                    # Double-check that date is still in the field
                    date_element = self.driver.find_element(By.XPATH, "//input[@placeholder='Select date']")
                    if date_element:
                        current_date = date_element.get_attribute('value') or ""
                        self.logger.info(f"Date verification before save: '{current_date}'")
                        
                        if current_date != date_value:
                            self.logger.warning(f"Date verification failed before save. Expected: '{date_value}', Got: '{current_date}'")
                            # Fix the date one more time
                            self.driver.execute_script("arguments[0].value = arguments[1];", date_element, date_value)
                            time.sleep(0.5)
                            self.logger.info(f"Fixed date before save: {date_value}")
                        else:
                            self.logger.info("Date verification passed - ready to save")
                except Exception as e:
                    self.logger.warning(f"Date verification failed: {e}")
            
            # 6.5. Verify notes were entered before saving
            if notes_content:
                try:
                    # Double-check that notes are actually in the field using the correct selector
                    notes_field = self.driver.find_element(By.XPATH, "//*[@data-test='ox-record-notes-field']")
                    if notes_field:
                        expected_notes = "\n".join(notes_content)
                        
                        # Check if it's a rich text editor (CKEditor)
                        if 'field-editor' in (notes_field.get_attribute('class') or ''):
                            self.logger.info("Verifying notes in rich text editor...")
                            # For CKEditor, we need to check the actual content
                            try:
                                # Try to get content from CKEditor instance
                                ckeditor_content = self.driver.execute_script("""
                                    if (window.CKEDITOR && window.CKEDITOR.instances) {
                                        for (var name in window.CKEDITOR.instances) {
                                            if (window.CKEDITOR.instances[name].element && 
                                                window.CKEDITOR.instances[name].element.$ === arguments[0]) {
                                                return window.CKEDITOR.instances[name].getData();
                                            }
                                        }
                                    }
                                    return null;
                                """, notes_field)
                                
                                if ckeditor_content:
                                    current_notes = ckeditor_content
                                    self.logger.info(f"Rich text editor - CKEditor content: '{current_notes}'")
                                else:
                                    # Fallback: check textContent
                                    current_notes = notes_field.get_attribute('textContent') or ""
                                    self.logger.info(f"Rich text editor - textContent: '{current_notes}'")
                                    
                            except Exception as ck_error:
                                self.logger.warning(f"CKEditor verification failed: {ck_error}")
                                current_notes = notes_field.get_attribute('textContent') or ""
                                self.logger.info(f"Rich text editor - fallback textContent: '{current_notes}'")
                        
                        # Check if it's contenteditable (rich text editor)
                        elif notes_field.get_attribute('contenteditable') == 'true':
                            current_notes = notes_field.get_attribute('innerHTML') or ""
                            self.logger.info(f"Contenteditable field - innerHTML: '{current_notes}'")
                        else:
                            current_notes = notes_field.get_attribute('value') or ""
                            self.logger.info(f"Regular field - value: '{current_notes}'")
                        
                        if current_notes != expected_notes:
                            self.logger.warning(f"Notes verification failed. Expected: '{expected_notes}', Got: '{current_notes}'")
                            # Try one more time to set notes using the appropriate method
                            if 'field-editor' in (notes_field.get_attribute('class') or ''):
                                self.logger.info("Attempting to fix notes in rich text editor...")
                                try:
                                    # Try CKEditor API first
                                    ckeditor_instance = self.driver.execute_script("""
                                        if (window.CKEDITOR && window.CKEDITOR.instances) {
                                            for (var name in window.CKEDITOR.instances) {
                                                if (window.CKEDITOR.instances[name].element && 
                                                    window.CKEDITOR.instances[name].element.$ === arguments[0]) {
                                                    return window.CKEDITOR.instances[name];
                                                }
                                            }
                                        }
                                        return null;
                                    """, notes_field)
                                    
                                    if ckeditor_instance:
                                        self.driver.execute_script("arguments[0].setData(arguments[1]);", ckeditor_instance, expected_notes)
                                        self.logger.info("Fixed notes using CKEditor setData")
                                    else:
                                        # Fallback to typing
                                        notes_field.click()
                                        time.sleep(0.5)
                                        notes_field.send_keys(Keys.CONTROL + "a")
                                        notes_field.send_keys(Keys.DELETE)
                                        time.sleep(0.5)
                                        notes_field.send_keys(expected_notes)
                                        self.logger.info("Fixed notes using typing method")
                                except Exception as fix_error:
                                    self.logger.warning(f"Failed to fix notes in rich text editor: {fix_error}")
                            elif notes_field.get_attribute('contenteditable') == 'true':
                                self.driver.execute_script("arguments[0].innerHTML = arguments[1];", notes_field, expected_notes)
                                self.logger.info("Attempted to fix notes using innerHTML")
                            else:
                                self.driver.execute_script("arguments[0].value = arguments[1];", notes_field, expected_notes)
                                self.logger.info("Attempted to fix notes using value")
                            time.sleep(1)
                        else:
                            self.logger.info("Notes verification passed - ready to save")
                except Exception as e:
                    self.logger.warning(f"Notes verification failed: {e}")
            
            # 7. Save the record
            try:
                self.logger.info("Looking for Save button...")
                
                # Wait a moment for any validation
                time.sleep(2)
                
                # The log shows the Save button exists in the list, so let's be more specific
                save_button = None
                
                # From the log: ['Open menu\nSR', 'Add record', 'Save', 'Clear form']
                # We know the Save button exists, so let's find it more systematically
                
                # First, get all buttons and find the one with 'Save' text
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                self.logger.info(f"Found {len(all_buttons)} total buttons")
                
                for i, btn in enumerate(all_buttons):
                    try:
                        if btn.is_displayed():
                            btn_text = btn.text.strip()
                            btn_classes = btn.get_attribute('class') or ""
                            self.logger.info(f"Button {i+1}: text='{btn_text}', classes='{btn_classes[:50]}...'")
                            
                            if btn_text == 'Save':
                                save_button = btn
                                self.logger.info(f"Found Save button: Button {i+1}")
                                break
                    except Exception as btn_error:
                        self.logger.warning(f"Error checking button {i+1}: {btn_error}")
                
                # Alternative selectors if the above doesn't work
                if not save_button:
                    save_selectors = [
                        "//button[normalize-space(text())='Save']",
                        "//button[contains(text(), 'Save')]",
                        "//button[text()='Save']",
                        "//input[@type='submit' and @value='Save']",
                        "//button[contains(@class, 'bg-primary') and contains(text(), 'Save')]"
                    ]
                    
                    for selector in save_selectors:
                        try:
                            save_button = self.driver.find_element(By.XPATH, selector)
                            if save_button.is_displayed() and save_button.is_enabled():
                                self.logger.info(f"Found Save button with selector: {selector}")
                                break
                        except:
                            continue
                
                if save_button:
                    try:
                        # Make sure it's visible and enabled
                        if save_button.is_displayed() and save_button.is_enabled():
                            # Scroll to button
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", save_button)
                            time.sleep(1)
                            
                            # Try JavaScript click first (most reliable)
                            self.driver.execute_script("arguments[0].click();", save_button)
                            self.logger.info("Clicked Save button using JavaScript")
                            
                            # Wait for save to complete
                            time.sleep(5)
                        else:
                            self.logger.error("Save button found but not displayed/enabled")
                            return None
                    except Exception as click_error:
                        self.logger.error(f"Error clicking Save button: {click_error}")
                        # Try regular click as fallback
                        try:
                            save_button.click()
                            self.logger.info("Clicked Save button using regular click")
                            time.sleep(5)
                        except Exception as regular_click_error:
                            self.logger.error(f"Regular click also failed: {regular_click_error}")
                            return None
                else:
                    self.logger.error("Could not find Save button with any method")
                    return None
                    
            except Exception as e:
                self.logger.error(f"Could not save record: {str(e)}")
                return None
            
            # 8. Extract record ID - IMPROVED VERSION
            record_id = None
            
            # Wait for save to complete and page to redirect
            for attempt in range(15):  # Try for up to 15 seconds
                try:
                    current_url = self.driver.current_url
                    self.logger.info(f"Attempt {attempt + 1}: Current URL: {current_url}")
                    
                    # Don't accept "new" as a valid record ID
                    if "/new" not in current_url:
                        # Check for record ID in URL
                        url_patterns = [
                            r'/records/([A-Z]+-[A-Z]?\d+)',  # OSOS-F00052 format
                            r'/records/(\d+)',  # Numeric ID
                            r'selected=([A-Z]+-[A-Z]?\d+)',  # In URL parameter
                            r'selected=(\d+)'  # Numeric in parameter
                        ]
                        
                        for pattern in url_patterns:
                            match = re.search(pattern, current_url)
                            if match:
                                potential_id = match.group(1)
                                # Make sure it's not "new"
                                if potential_id != "new" and len(potential_id) > 2:
                                    record_id = potential_id
                                    self.logger.info(f"Found record ID in URL: {record_id}")
                                    break
                        
                        if record_id:
                            break
                    
                    time.sleep(1)
                    
                except Exception as e:
                    self.logger.warning(f"Error checking URL: {e}")
            
            # If no record ID from URL, try to find it in page content
            if not record_id:
                try:
                    time.sleep(3)
                    
                    # Look for the "Last created" element we see in the image
                    try:
                        # From the image, we see "Last created: OSOS-F00052"
                        last_created_element = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Last created')]")
                        if last_created_element.is_displayed():
                            # Look for the record ID near this element
                            parent = last_created_element.find_element(By.XPATH, "./..")
                            record_links = parent.find_elements(By.XPATH, ".//*[contains(text(), 'OSOS-F')]")
                            if record_links:
                                record_id = record_links[0].text.strip()
                                self.logger.info(f"Found record ID from 'Last created': {record_id}")
                    except:
                        pass
                    
                    # Alternative: look in page source
                    if not record_id:
                        page_source = self.driver.page_source
                        
                        # Look for Archive Ox record patterns
                        id_patterns = [
                            r'(OSOS-F\d+)',
                            r'([A-Z]+-F\d+)',
                            r'(OSOS-\d+)'
                        ]
                        
                        for pattern in id_patterns:
                            matches = re.findall(pattern, page_source)
                            if matches:
                                # Get the most recent/highest numbered record
                                record_id = max(matches, key=lambda x: int(''.join(filter(str.isdigit, x))))
                                self.logger.info(f"Found record ID in page content: {record_id}")
                                break
                                
                except Exception as e:
                    self.logger.warning(f"Could not extract record ID from page: {str(e)}")
            
            # Return record ID or generate fallback
            if record_id and record_id != "new":
                self.logger.info(f"Successfully created record for {file_path}, got record ID: {record_id}")
                return record_id
            else:
                # Generate fallback ID with timestamp
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fallback_id = f"{project_name or 'OSOS'}_{timestamp}"
                self.logger.warning(f"Could not extract record ID for {file_path}, using fallback: {fallback_id}")
                return fallback_id
            
        except Exception as e:
            self.logger.error(f"Failed to create record for {file_path}: {str(e)}")
            return None
    
    def rename_file_with_serial(self, original_path, record_id, naming_pattern="{serial}_{name}{ext}"):
        """Rename file with Archive Ox record ID"""
        try:
            path_obj = Path(original_path)
            
            # Create new filename
            new_name = naming_pattern.format(
                name=path_obj.stem,
                serial=record_id,
                ext=path_obj.suffix
            )
            
            new_path = path_obj.parent / new_name
            
            # Rename the file
            shutil.move(str(path_obj), str(new_path))
            
            self.logger.info(f"Renamed {original_path} to {new_path}")
            return str(new_path)
            
        except Exception as e:
            self.logger.error(f"Failed to rename {original_path}: {str(e)}")
            return None
    
    def process_batch(self, file_paths, source_info="", naming_pattern="{serial}_{name}{ext}", record_type="auto", project_name="", copyright_owner="", date_value="", notes="", on_progress=None):
        """Process a batch of files - create records and rename local files"""
        self.logger.info(f"=== BATCH PROCESSING DEBUG ===")
        self.logger.info(f"Notes parameter received: '{notes}'")
        self.logger.info(f"Source info: '{source_info}'")
        self.logger.info(f"Project: '{project_name}'")
        self.logger.info(f"Copyright: '{copyright_owner}'")
        self.logger.info(f"Date: '{date_value}'")
        self.logger.info(f"Record type: '{record_type}'")
        self.logger.info(f"Number of files: {len(file_paths)}")
        self.logger.info(f"=== END BATCH DEBUG ===")
        
        results = []
        
        for i, file_path in enumerate(file_paths):
            try:
                msg = f"Processing file {i+1}/{len(file_paths)}: {os.path.basename(file_path)}"
                print(msg)
                if on_progress:
                    on_progress(i, len(file_paths), msg)
                
                # Auto-detect record type if needed
                if record_type == "auto":
                    file_ext = Path(file_path).suffix.lower()
                    if file_ext in ['.mp4', '.mov', '.avi', '.mkv', '.wmv']:
                        current_record_type = "Footage"
                    elif file_ext in ['.mp3', '.wav', '.aac', '.flac']:
                        current_record_type = "Audio"
                    elif file_ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
                        current_record_type = "Still"
                    else:
                        current_record_type = "Footage"  # Default
                else:
                    current_record_type = record_type
                
                # Create record in Archive Ox (metadata only)
                record_id = self.upload_file_to_archive_ox(
                    file_path, 
                    source_info, 
                    current_record_type, 
                    project_name, 
                    copyright_owner, 
                    date_value,
                    notes
                )
                
                if record_id:
                    # Rename the local file with Archive Ox record ID
                    new_path = self.rename_file_with_serial(file_path, record_id, naming_pattern)
                    
                    results.append({
                        'original_path': file_path,
                        'new_path': new_path,
                        'record_id': record_id,
                        'project': project_name,
                        'copyright': copyright_owner,
                        'date': date_value,
                        'record_type': current_record_type,
                        'status': 'success'
                    })
                else:
                    results.append({
                        'original_path': file_path,
                        'new_path': None,
                        'record_id': None,
                        'project': project_name,
                        'copyright': copyright_owner,
                        'date': date_value,
                        'record_type': current_record_type,
                        'status': 'failed'
                    })
                
                # Longer delay to ensure form resets properly between files
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error processing {file_path}: {str(e)}")
                results.append({
                    'original_path': file_path,
                    'new_path': None,
                    'record_id': None,
                    'project': project_name,
                    'copyright': copyright_owner,
                    'date': date_value,
                    'record_type': record_type,
                    'status': 'error',
                    'error': str(e)
                })
        
        return results
    
    def save_results(self, results, output_file="batch_results.json"):
        """Save processing results to file"""
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        self.logger.info(f"Results saved to {output_file}")
    
    def cleanup(self):
        """Close browser and cleanup"""
        if self.driver:
            self.driver.quit()

