import json
import logging
import math
import os
import threading
from time import sleep
import tkinter as tk
from tkinter import ttk
import requests
from typing import Any, Mapping, MutableMapping, Optional
from config import config, appname
from theme import theme
from threading import Thread
import launcher

version='1.0.0'
plugin_name = os.path.basename(os.path.dirname(__file__)) +'-'+ version
logger = logging.getLogger(f'{appname}.{plugin_name}')
URL = "http://127.0.0.1:5005/"

# If the Logger has handlers then it was already set up by the core code, else
# it needs setting up here.
if not logger.hasHandlers():
    level = logging.DEBUG  # So logger.info(...) is equivalent to print()

    logger.setLevel(level)
    logger_channel = logging.StreamHandler()
    logger_formatter = logging.Formatter(f'%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d:%(funcName)s: %(message)s')
    logger_formatter.default_time_format = '%Y-%m-%d %H:%M:%S'
    logger_formatter.default_msec_format = '%s.%03d'
    logger_channel.setFormatter(logger_formatter)
    logger.addHandler(logger_channel)
    
class CThis:
    """Holds module globals."""

    def __init__(self):
        self.signal_array = []
        self.coort_array = []
        self.signal_rate = 44100
        self.lbl: Optional[tk.Label]
        self.lbl_signal: Optional[tk.Label]
        self.frame: Optional[tk.Frame]
        self.canvas: Optional[tk.Canvas]
        self.combo: Optional[ttk.Combobox]
        self.btServer: Optional[tk.Button]
        self.btStart: Optional[tk.Button]
        self.btRealtime: Optional[tk.Button]
        self.btCoort: Optional[tk.Button]
        self.btSpectrum: Optional[tk.Button]
        self.width = 300
        self.height = 75
        self.thread: Optional[threading.Thread] = None
        self.session = requests.Session()
        self.min = .0
        self.max = .0
        self.getout = False
        self.devices = [] # [(name, id, sample_rate)]
        self.mode = 1
        self.last_divide = 0
        
        
this = CThis()
pouet = this


def plugin_start3(plugin_dir: str) -> str:
    return plugin_name
    

def get_devices_list():
    """
    R??cup??re la liste des devices et rempli la combo
    """
    try:
        ans = requests.get(URL + 'getDevices', timeout=3)
        if ans.status_code == 200:
            this.devices = json.loads(ans.json())
            vals = []
            # (name, id, sample_rate)
            for c in this.devices:
                vals.append(c[0])
            this.combo.config(values=vals)
            this.btStart["state"] = tk.NORMAL
            this.btRealtime["state"] = tk.NORMAL
            this.btCoort["state"] = tk.NORMAL
            this.btSpectrum["state"] = tk.NORMAL
            this.lbl.config(text=plugin_name + " - Choose device.")
            theme.update(this.frame)
        else:
            logger.debug("Server comm error")
    except Exception as e:
        logger.debug("Server unavailable")
        this.lbl.config(text=plugin_name + " - Starting service...")
        launcher.launch_server()
        sleep(3)
        get_devices_list()
    
    
def set_device():
    """
    Envoi au serveur le device ?? utiliser
    Returns:
        bool: true si succes
    """
    # logger.debug(f'set_device - {this.combo.get()}')
    try:
        if not this.devices or not this.combo.get() or len(this.combo.get()) < 1:
            return False
        for d in this.devices:
            if d[0] in this.combo.get():
                dev_id = d[1]
                this.signal_rate = int(d[2])
                break
        if not dev_id:
            return False
    
        ans = requests.post(URL + 'setDevice',
                            json=json.dumps(dict(id=dev_id)),
                            timeout=1)
        if ans.status_code == 200:
            rep = ans.json()
            if rep["ans"]:
                return True
            else:
                this.lbl.config(text=plugin_name + " - Incorrect device.")
        else:
            logger.debug("Communication avec le server impossible")
    except Exception as e:
        logger.debug("Erreur de traitement de la r??ponse", exc_info=e)
        this.lbl.config(text=plugin_name + " - Server down.")
    return False
    
def check_thread_state():
    """
    V??rifie l'??tat courant de l'??coute et stop le cas ??ch??ant
    """
    if this.thread and this.thread.is_alive():
        this.getout = True
        sleep(0.5)
    
    
def start_listening():
    """
    D??marre le thread d'??coute
    """
    check_thread_state()
    # logger.debug('Starting worker thread...')
    this.thread = Thread(target=worker, name='C14 worker')
    this.thread.daemon = True
    this.thread.start()
    # logger.debug('Done.')

def plugin_stop():
    """
    EDMC is closing
    """
    this.getout = True
    try:
        requests.post(URL + 'shutdown', timeout=0.2)
    except Exception as e:
        """ """
    # logger.debug("Stopping the plugin")

def start_thread():
    """
    Envoi les param??tres et lance l'??coute si ok
    """
    check_thread_state()
    set_mode_realtime()
    ok = set_device()
    # logger.debug(f'start_thread ok={ok}')
    if ok:
        start_listening()
        
    
def start_command():
    """
    Commande appel??e depuis le bouton.
    D??marre un thread de setDevice puis start_listening si OK
    """
    # logger.debug(f'start_command')
    try:
        th = Thread(target=start_thread, name='C14 start_thread')
        th.daemon = True
        th.start()
    except Exception as e:
        logger.debug("start_command", exc_info=e)
    
def set_mode(mode):
    """
    D??finit le mode d'affichage
    Args:
        mode (int): 1, 2 ou 3
    """
    #  mise ?? jour que si le mode est diff??rent
    if this.mode != mode:
        this.canvas.delete("all")
        this.coort_array = []
        this.signal_array = []
        this.last_divide = 0
        # on envoi la maj du mode en cas de spectrum
        try:
            if mode < 3:
                # mode wave
                ans = requests.post(URL + 'setSpectrumMode', 
                                    json=json.dumps(dict(active=False)),
                                    timeout=1)
            else:
                # mode spectrum
                ans = requests.post(URL + 'setSpectrumMode', 
                                    json=json.dumps(dict(active=True)),
                                    timeout=1)
            if ans.status_code != 200:
                this.lbl.config(text=plugin_name + " - Mode error")

        except Exception as e:
            logger.debug('Exception set_mode', exc_info=e)
            this.lbl.config(text=plugin_name + " - Server down.")
            
    this.mode = mode

    
    
def set_mode_realtime():
    set_mode(1)
    
def set_mode_cohort():
    set_mode(2)
    
def set_mode_spectrum():
    set_mode(3)
    
def start_server():
    """ D??marre le serveur d'??coute """
    this.btServer.destroy()
    
    this.combo = ttk.Combobox(this.frame, width=40)
    this.combo.grid(row=1, sticky=tk.W, column=0)
    
    this.btStart = tk.Button(this.frame, text=">", command=start_command, padx=4, state=tk.DISABLED)
    this.btStart.grid(row=1, sticky=tk.E, column=1)
    
    this.canvas = tk.Canvas(this.frame, width=this.width, height=this.height)
    this.canvas.grid(row=2,sticky=tk.W, columnspan=2, column=0)
    this.canvas.bind_all('<<C14Update>>', update_canvas)
    
    btFrame = tk.Frame(this.frame)
    btFrame.grid(row=3,sticky=tk.SE, columnspan=2, column=0)
    btFrame.columnconfigure(0, weight=1)
    btFrame.columnconfigure(1, weight=1)
    btFrame.columnconfigure(2, weight=1)
    btFrame.columnconfigure(3, weight=1)
    
    this.btRealtime = tk.Button(btFrame, text="realtime", command=set_mode_realtime, padx=4, state=tk.DISABLED)
    this.btRealtime.grid(row=0, sticky=tk.E, column=1)
    this.btCoort = tk.Button(btFrame, text="cohort", command=set_mode_cohort, padx=4, state=tk.DISABLED)
    this.btCoort.grid(row=0, sticky=tk.E, column=2, padx=5)
    this.btSpectrum = tk.Button(btFrame, text="spectrogram", command=set_mode_spectrum, padx=4, state=tk.DISABLED)
    this.btSpectrum.grid(row=0, sticky=tk.E, column=3)
    
    theme.update(btFrame)
    theme.update(this.frame)
    
    th = Thread(target=get_devices_list, name='C14 get_devices_list')
    th.daemon = True
    th.start()
    

def plugin_app(parent: tk.Frame) -> tk.Frame:
    """
    TK widgets for the EDMarketConnector main window
    """
    this.frame = tk.Frame(parent)
    this.frame.columnconfigure(0, weight=7)
    this.frame.columnconfigure(1, weight=1)
    this.lbl = tk.Label(this.frame, text="C14 Sound visualizer")
    this.lbl.grid(row=0, sticky=tk.N, columnspan=2, column=0)
    
    this.btServer = tk.Button(this.frame, text="Start server", command=start_server, padx=4, pady=4)
    this.btServer.grid(row=1, sticky=tk.E+tk.W+tk.N+tk.S)
        
    theme.update(this.frame)    
    return this.frame



def update_canvas(event=None) -> None:
    """Update the canvas displaying results"""
    # logger.debug("Enter update canvas")
    signal = this.signal_array.copy()
    this.signal_array = []
    """Coordinates computation for display"""
    count = len(signal)
    # logger.debug(f'len of array = {count}')
    if count < 1:
        return
    
    if this.mode < 3:
        # logger.debug(f'compute scaling')
        """ scaling Y """
        maxVal = max(signal)
        if maxVal > this.max:
            this.max = maxVal
        minVal = min(signal)
        if minVal < this.min:
            this.min = minVal
            
        # maximum = max(abs(this.max), abs(this.min))
        maximum = 100
        bias = (this.height / 2)
        if maximum == 0:
            coef = 1
        else:
            coef = -bias / maximum
        
    if this.mode == 1:
        display_realtime(signal, coef, bias)
    elif this.mode == 2:
        display_coort(signal, coef, bias)
    else:
        display_mel_spectrum(signal)
        

def display_realtime(signal, coef, bias):
    """
    Affichage par d??faut en temps r??el
    """
    # logger.debug("draw canvas")
    count = len(signal)
    this.canvas.delete("all")        
    for i in range(0, count-1):
        # dessin dans l'immediat
        x0 = int(i * this.width / (count-1))
        y0 = int(coef * signal[i] + bias)
        x1 = int((i+1) * this.width / (count-1))
        y1 = int(coef * signal[i+1] + bias)
        # logger.debug(f'p({x0}, {y0}) -> p({x1}, {y1})')
        this.canvas.create_line(x0, y0, 
                                x1, y1,
                                fill="orange", activefill="orange")

        
def display_coort(signal, coef, bias):
    """
    Affichage en mode coort
    """
    count = len(signal)
    if len(this.coort_array) >= this.signal_rate:
        this.canvas.delete("all")
        this.coort_array = []
        start = 0
    else:
        start = len(this.coort_array)
    # dessin dans la coort
    for i in range(0, count-1):
        x0 = int((start + i) * this.width / this.signal_rate)
        y0 = int(coef * signal[i] + bias)
        x1 = int((start + i+1) * this.width / this.signal_rate)
        y1 = int(coef * signal[i+1] + bias)
        this.coort_array.append(((x0,y0),(x1,y1)))
        this.canvas.create_line(x0, y0,
                            x1, y1,
                            fill="cyan", activefill="cyan")

    
def max_list(list):
    """
    Calcul la valeur maximale d'une liste
    """
    if not list or len(list) < 1:
        return 0

    return max(list)

def display_mel_spectrum(signal):
    """
    Affichage du spectrogramme en ??chelle MEL
    """
    # logger.debug("display_spectrum")
    # reset
    if this.last_divide >= this.width:
        this.last_divide = 0
        this.canvas.delete("all")
    x = this.last_divide
    y_prev = this.height
    B = this.height
    A = -this.height / len(signal)
    # pixel skip : we're not displaying the full spectrum over time in order to have a better overview.
    # at the current sample rate of 48000, to display 7 sec of recording in 300 pixels, you have to skip
    # 1 / 2 values.
    skip = 1
    for i in range(0, len(signal) -1):
        try:
            colours = signal[i]
            # this really bothers me.
            if isinstance(colours, int):
                # get out! son of a...
                continue
            
            yB = y_prev
            yH = (i+1)*A +B
            y_prev = yH
            w = 0
            cn = 0
            for col in colours:
                # skipping values to shorten the render
                if cn < skip:
                    cn +=1
                    continue
                cn = 0
                try:
                    x = int(this.last_divide + w)
                    if x > this.width:
                        break
                    
                    w += 1
                    # dessin d'une ligne verticale
                    this.canvas.create_line(
                        x, yB,
                        x, yH,
                        fill=get_spectrum_color(col)
                    )
                except Exception as e:
                    logger.debug("Erreur de calcul X", exc_info=e)
        except Exception as e2:
            logger.debug(f'Erreur de calcul Y: {i} > {len(signal)} ({type(signal)})', exc_info=e2)
                            
    this.last_divide = x+1

def get_spectrum_color(col) -> str:
    """
    Calcul la couleur en hexa depuis un float
    """
    loc = col
    if math.isinf(loc) or math.isnan(loc):
        loc = 0
        # logger.debug(f'inf ou nan = {colours}')

    if loc > 255:
        loc = 255
        # logger.debug(f'{col} > 255')

    c = hex(255-int(loc))[2::]
    ans='#'+c+c+c
    # logger.debug(f'color={ans}, col={col}')
    return ans

            
def worker() -> None:
    """
    Thread that handle sound recording and data update for canvas display
    """
    # logger.debug('Thread starting...')
    
    # on ance le streaming
    this.lbl.config(text=plugin_name + " - Starting stream")
    try:
        ans = requests.get(URL + 'startstream', timeout=1)
        sleep(1)
        if ans.status_code != 200:
            pouet.getout = True
            this.lbl.config(text=plugin_name + " - Stream error")
        else:
            pouet.getout = False
            this.lbl.config(text=plugin_name + " - Waiting server")
    except Exception as e:
        logger.debug('Exception dans traitement', exc_info=e)
        pouet.getout = True        
    
    fps = 50 # Cocorico.
    while not pouet.getout:
        # local_mode = pouet.mode
        try:
            ans = requests.get(URL + 'audiovalues', timeout=1)
            sleep(1/fps)
            if ans.status_code == 200:
                content = []
                content = json.loads(ans.json())
                if content and type(content) is list and len(content) > 1:
                    this.lbl.config(text=plugin_name + " - Listening")
                else:
                    this.lbl.config(text=plugin_name + " - Waiting server")
                    sleep(1)
                    continue
                
                pouet.signal_array = []
                for i in content:
                    if type(i) is list:
                        # garde fou
                        if pouet.mode != 3:
                            break
                        # spectrogramme
                        pouet.signal_array.append(i)
                    else:
                        # garde fou
                        if pouet.mode > 2:
                            break
                        # wave
                        pouet.signal_array.append(int(i))
                        # pouet.signal_array.append(randint(-100,100))
                        if len(pouet.signal_array) == int(pouet.signal_rate / fps):
                            # logger.debug(f'signal_array size={len(pouet.signal_array)}, send event to update')
                            pouet.canvas.event_generate('<<C14Update>>', when="now")
                            sleep(1/fps)
                        
                if len(pouet.signal_array) > 0:
                    pouet.canvas.event_generate('<<C14Update>>', when="now")
                    if pouet.mode == 3:
                        sleep(1)
                    else:
                        sleep(1/fps)
            else:
                logger.debug('Serveur indisponible')
                this.lbl.config(text=plugin_name + " - Error")
                pouet.getout = True
                break
        except Exception as e:
            logger.info('Server request timeout')
            this.lbl.config(text=plugin_name + " - Crashed")
            pouet.getout = True
            break
    
    """ closure """
    # logger.debug('End of Thread C14')

        