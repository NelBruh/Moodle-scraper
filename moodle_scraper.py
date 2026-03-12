from bs4 import BeautifulSoup as BS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import requests
import dotenv
import os
import re
import time

class Moodle_Scraper:
    
    

    def __init__(self):
    
        """
        Moodle_Scraper Class Constructor
            Builds the Moodle_Scraper object
            Needs .env file with "usuario" and "pw"
        """
        
        #user and password for Moodle
        self.user = dotenv.get_key(".env", "usuario")  
        self.pw = dotenv.get_key(".env", "pw")         

        #FilePath setup
        self.base_path = "moodle"
        self.course_path = ""
        self.section_path = ""
        
        #Selenium driver
        self.driver = self.setup_driver()
        
        #requests session
        self.session = requests.Session()
    
    
    

    
    def setup_driver(self):
        """
        Sets up the selenium Chrome driver
            Returns:
                None
        """
        
        options =  Options()
        
        options.add_experimental_option("prefs", {
            "download.prompt_for_download": False,       #dont ask for permission to download
            "plugins.always_open_pdf_externally": True,  # forces download
            "download.conflict_action": "overwrite"      #overwrites same name file 
        })
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--headless")
        
        return webdriver.Chrome(options=options)
    




    def login(self):
        """
        Logs into moodle.upm.es using selenium
        Extracts the cookies and sets up the requests session
            Returns:
                None
        """
        
        driver = self.driver
        user = self.user
        pw = self.pw
        
        #login
        url = "https://moodle.upm.es/titulaciones/oficiales/login/login.php"
        driver.get(url = url)
        driver.find_element(By.ID, "boton_cas").click()
        driver.find_element(By.ID, "username").send_keys(user)
        driver.find_element(By.ID, "password").send_keys(pw)
        driver.find_element(By.ID, "kc-login").click()
        WebDriverWait(driver, 30).until(
            EC.url_contains("moodle.upm.es/titulaciones/oficiales/my/")
        )
        
        #extract cookies and setup requests session
        self.cookies = driver.get_cookies()
        self.setup_session()
    




    def setup_session(self):
        """
        Sets up the requests session with the extracted cookies
        Extracts the session key
            Returns:
                None
        """
        
        for cookie in self.cookies:
            self.session.cookies.set(cookie["name"], cookie["value"], domain="moodle.upm.es")
        self.sesskey = self.driver.execute_script("return M.cfg.sesskey")
    
    
    
    

    def get_courses(self):
        """
        Extracts the course name and the URL
            Returns:
                dict{
                    course name : course URL
                    }
        """
        
        sesskey = self.sesskey
        session = self.session
        
        #extract the name of the courses and the URL
        url = f"https://moodle.upm.es/titulaciones/oficiales/lib/ajax/service.php?sesskey={sesskey}&info=core_course_get_enrolled_courses_by_timeline_classification"
        body = [{"index":0,"methodname":"core_course_get_enrolled_courses_by_timeline_classification","args":{"offset":0,"limit":24,"classification":"all","sort":"fullname","customfieldname":"","customfieldvalue":"","requiredfields":["id","fullname","shortname","showcoursecategory","showshortname","visible","enddate"]}}]
        response = session.post(url, json = body)
        json = response.json()
        courses = {}
        for course in json[0]["data"]["courses"]:
            courses[course["fullname"]] = course["viewurl"]
            
        #remove the Student Documentation
        courses.pop("Ayuda y documentación para estudiantes")
        
        self.courses = courses
        return courses
    





    def get_sections(self, course_url):
        """
        Extract the sections from the course
        Creates directories for each section
        Downloads the file in that directory
            Args:
                course_url: the URL for the course
            Returns:
                None
        
        """
        
        driver = self.driver
        base_path = self.base_path
        course_path = self.course_path
        
        
        #get html for the course page
        driver.get(course_url)
        html = driver.page_source
        soup = BS(html, "html.parser")
        
        #get the sections, their names and create the directory
        secciones = soup.find_all("li", attrs={"data-for" : "section"})
        secciones_path = []
        i = 1
        for seccion in secciones:
            h3 = seccion.find("h3")
            a = h3.find("a")
            self.section_path = f"{i}.{a.text}".strip()
            i += 1
            self.download_path = self.clean_path(os.path.join(base_path, course_path, self.section_path))
            secciones_path.append(self.download_path)
            os.makedirs(self.download_path, exist_ok=True)
        
        #scrape the files for each section
        i = 0    
        for seccion in secciones:
            driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": os.path.abspath(secciones_path[i])
            })
            self.download_files(seccion)
            self.download_wait(secciones_path[i], 30)
            i += 1





    def download_files(self, seccion):
        """
        Download the files
            Args:
                seccion: the section to scrape
            Returns:
                None
        """
        
        driver = self.driver  
        
        seccion_archivos = seccion.find_all("li", attrs={"data-for" : "cmitem"})
        for archivos in seccion_archivos:
            tag_descarga = archivos.find("a", onclick = True)
            if(tag_descarga != None and tag_descarga != ""):
                onclick = tag_descarga.get("onclick")
                if(onclick != None and onclick != ""):
                    link_descarga = re.search(r"'(https?://[^']+)'", tag_descarga.get("onclick")).group(1)
                    driver.get(link_descarga)
    
    
    
    
    
    def download_wait(self, path, timeout):
        """
        waits for the download in the current path to end
            Args:
                path: the path where the files are downloaded into
                
                timeout: how much time in seconds to wait
            Return:
                None 
        """
        
        sec = 0
        while sec < timeout:
            #checks if theres any file with .crdownload (chromiun temp download file)
            if not any(f.endswith(".crdownload") for f in os.listdir(path)):
                return
            else:
                sec += 1
                time.sleep(1)
        




    def scrape(self):
        """
        Calls all the functions to scrape moodle
            Returns:
                None
        """ 
        
        self.setup_driver()
        self.login()
        courses = self.get_courses()
        for course in courses:
            self.course_path = course.strip() #no spaces at the end or beginning allowed
            os.makedirs(self.clean_path(os.path.join(self.base_path, course)), exist_ok= True)
            self.get_sections(courses[course])
        print("Exito \n")
        time.sleep(10)
        self.quit()





    def quit(self):
        """
        Ends the selenium driver
            Returns:
                None
        """
        
        self.driver.quit()
    
    
    
    

    def clean_path(self, name):
        """
        Cleans the path String to a format accepted by Windows
        file system
            Args:
                name: the path string to clean
            Returns:
                None 
        """
        
        return re.sub(r'[<>:"/|?*]', '', name).strip()
