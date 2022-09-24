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

plugin_name = os.path.basename(os.path.dirname(__file__))
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
        self.frame_signal: Optional[tk.Frame]
        self.canvas: Optional[tk.Canvas]
        self.combo: Optional[ttk.Combobox]
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
        self.map_ids = []
        self.map_belt_ids = []
        self.mapped = list((0,0))
        self.map_bodies = list((0,0))
        self.map_geo = 0
        self.map_bio = 0
        self.map_rings = 0
        self.map_belts = 0
        self.map_signals = 0
        self.map_UIA = 3
        self.map_others = list((0,0))
        self.map_new_scan = False
        
        
this = CThis()
pouet = this


def plugin_start3(plugin_dir: str) -> str:
    return plugin_name
    

def get_devices_list():
    """
    Récupère la liste des devices et rempli la combo
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
    Envoi au serveur le device à utiliser
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
        logger.debug("Erreur de traitement de la réponse", exc_info=e)
        this.lbl.config(text=plugin_name + " - Server down.")
    return False
    
def check_thread_state():
    """
    Vérifie l'état courant de l'écoute et stop le cas échéant
    """
    if this.thread and this.thread.is_alive():
        this.getout = True
        sleep(0.5)
    
    
def start_listening():
    """
    Démarre le thread d'écoute
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
    Envoi les paramètres et lance l'écoute si ok
    """
    check_thread_state()
    set_mode_realtime()
    ok = set_device()
    # logger.debug(f'start_thread ok={ok}')
    if ok:
        start_listening()
        
    
def start_command():
    """
    Commande appelée depuis le bouton.
    Démarre un thread de setDevice puis start_listening si OK
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
    Définit le mode d'affichage
    Args:
        mode (int): 1, 2 ou 3
    """
    #  mise à jour que si le mode est différent
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

def plugin_app(parent: tk.Frame) -> tk.Frame:
    """
    TK widgets for the EDMarketConnector main window
    """
    this.frame = tk.Frame(parent)
    this.frame.columnconfigure(0, weight=7)
    this.frame.columnconfigure(1, weight=1)
    this.lbl = tk.Label(this.frame, text="Sound visualizer")
    this.lbl.grid(row=0, sticky=tk.N, columnspan=2, column=0)
    
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
    
    this.lbl_signal = tk.Label(btFrame, text="Signals: ?")
    this.lbl_signal.grid(row=0, sticky=tk.W, column=0, padx=10)
    this.btRealtime = tk.Button(btFrame, text="realtime", command=set_mode_realtime, padx=4, state=tk.DISABLED)
    this.btRealtime.grid(row=0, sticky=tk.E, column=1)
    this.btCoort = tk.Button(btFrame, text="cohort", command=set_mode_cohort, padx=4, state=tk.DISABLED)
    this.btCoort.grid(row=0, sticky=tk.E, column=2, padx=5)
    this.btSpectrum = tk.Button(btFrame, text="spectrogram", command=set_mode_spectrum, padx=4, state=tk.DISABLED)
    this.btSpectrum.grid(row=0, sticky=tk.E, column=3)
    
    this.frame_signal = tk.Frame(this.frame, border=None)
    this.frame_signal.grid(row=4,sticky=tk.SW, columnspan=2, column=0)
    
    theme.update(this.frame)
    # this.frame.pack(side='top', fill="x", expand=False)
    
    # on commence par request les devices
    # et remplir la combo
    th = Thread(target=get_devices_list, name='C14 get_devices_list')
    th.daemon = True
    th.start()
    
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
    Affichage par défaut en temps réel
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
    Calcul la valeur médiane d'une liste
    """
    if not list or len(list) < 1:
        return 0

    return max(list)


def display_mel_spectrum(signal):
    """
    Affichage du spectrogramme en échelle MEL
    """
       # logger.debug("display_spectrum")
    # reset
    if this.last_divide >= this.width:
        this.last_divide = 0
        this.canvas.delete("all")

    # on a un certain nombre de dB (128) x 87 samples pour 1 seconde d'échantillonnage serveur
    # il faudrait afficher 10 secondes pour avoir les signaux thargo de 7s
    nbseconde = 6
    # signal[[color value in time]]
    divide = this.width / (nbseconde * len(signal[0]))
    # nbSample contient le nombre de Sxx à prendre en compte pour dessiner 1pxl
    nbSample = math.ceil(1 / divide)
    x = this.last_divide
    y_prev = this.height
    B = this.height
    A = -this.height / len(signal)
    for i in range(0, len(signal) -1):
        try:
            yB = y_prev
            yH = (i+1)*A +B
            y_prev = yH
            w = 0
            colours = signal[i]
            for j in range(0, len(colours), nbSample):
                try:
                    med = max_list(colours[j : j+nbSample])
                    x = int(this.last_divide + w)
                    w += 1
                    # dessin d'une ligne puisqu'on a qu'un seul pixl en X à chaque fois!
                    this.canvas.create_line(
                        x, yB,
                        x, yH,
                        fill=get_spectrum_color(med)
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

    
def update_signals_frame():
    """ maj des signaux affichés """
    this.lbl_signal.config(text="Total: "+str(this.mapped[0])+"/"+str(this.mapped[1]))

    this.frame_signal.destroy()
    this.frame_signal = tk.Frame(this.frame, border=None)
    this.frame_signal.grid(row=4,sticky=tk.SW, columnspan=2, column=0)

    col = 0

    if this.map_bodies[1] > 0:
        lbl = tk.Label(this.frame_signal, text="Bodies: "+str(this.map_bodies[0])+"/"+str(this.map_bodies[1]))
        lbl.grid(row=0, column=col, sticky=tk.W)        
        col+=1
    if this.map_others[1] > 0:
        lbl = tk.Label(this.frame_signal, text="Others: "+str(this.map_others[0])+"/"+str(this.map_others[1]))
        lbl.grid(row=0, column=col, sticky=tk.W, padx=4)
        col+=1
    if this.map_UIA > 0:
        lbl = tk.Label(this.frame_signal, text="UIA: "+str(this.map_UIA))
        lbl.grid(row=0, column=col, sticky=tk.W, padx=4)
        col+=1
    if this.map_belts > 0:
        lbl = tk.Label(this.frame_signal, text="Asteroids: "+str(this.map_belts))
        lbl.grid(row=0, column=col, sticky=tk.W, padx=4)

    col=0
    if this.map_geo > 0:
        lbl = tk.Label(this.frame_signal, text="Geological: "+str(this.map_geo))
        lbl.grid(row=1, column=col, sticky=tk.W)
        col+=1
    if this.map_bio > 0:
        lbl = tk.Label(this.frame_signal, text="Biological: "+str(this.map_bio))
        lbl.grid(row=1, column=col, sticky=tk.W, padx=4)
        col+=1
    if this.map_rings > 0:
        lbl = tk.Label(this.frame_signal, text="Rings: "+str(this.map_rings))
        lbl.grid(row=1, column=col, sticky=tk.W)
        
    col=0
    if this.map_signals > 0:
        lbl = tk.Label(this.frame_signal, text="Signals: "+str(this.map_signals))
        lbl.grid(row=0, column=col, sticky=tk.W, padx=4)
        col+=1
        
    theme.update(this.frame_signal)

    
def journal_entry(
    cmdr: str, is_beta: bool, system: str, station: str, entry: MutableMapping[str, Any], state: Mapping[str, Any]
) -> None:
    if entry['event'] == 'FSDJump':
        # We arrived at a new system!
        this.lbl_signal.config(text="Signals: ?")
        this.map_ids = []
        this.map_belt_ids = []
        this.mapped[0] = 0
        this.mapped[1] = 0
        this.map_bodies[0] = 0
        this.map_bodies[1] = 0
        this.map_others[0] = 0
        this.map_others[1] = 0
        this.map_geo = 0
        this.map_bio = 0
        this.map_rings = 0
        this.map_belts = 0
        this.map_signals = 0
        this.map_UIA = 3
        this.map_new_scan = False
        update_signals_frame()
        
    if entry['event'] == 'FSSDiscoveryScan':
        # maj du nombre de scan attendu
        this.map_bodies[1] = int(entry['BodyCount'])
        this.map_others[1] = int(entry['NonBodyCount'])
        this.map_others[0] += this.map_UIA
        this.mapped[1] = this.map_bodies[1] + this.map_others[1]
        this.mapped[0] += this.map_UIA
        if not this.map_new_scan:
            this.mapped[0] += int(entry['Progress'] * this.map_bodies[1])
            this.map_bodies[0] = int(entry['Progress'] * this.map_bodies[1])
        update_signals_frame()
        
    if entry['event'] == 'Scan':
        this.map_new_scan = True
        bId = entry['BodyID']
        update = False
        if 'Belt' in entry['BodyName']:
            if bId not in this.map_belt_ids:
                # Ceinture d'astéroid non mappé
                this.map_belt_ids.append(bId) 
                this.map_belts += 1
                this.map_others[0] += 1
                this.mapped[0] += 1
                update = True
        elif bId not in this.map_ids:
            # body non mappé
            this.map_ids.append(bId)
            this.map_bodies[0] += 1
            this.mapped[0] += 1
            update = True
            
        if 'Rings' in entry:
            # on a découvert des signaux d'anneaux de type other si belt
            for ring in entry['Rings']:
                if 'Belt' not in ring['Name']:
                    this.map_rings += 1
                    # this.mapped[0] += 1
                    # this.map_others[0] += 1
                
            update = True
        
        if update:
            update_signals_frame()
            
    if entry['event'] == 'FSSBodySignals':
        if 'Signals' in entry:
            for sgnl in entry['Signals']:
                # on détermine le type et le count
                if 'Geological' in sgnl['Type']:
                    this.map_geo += sgnl['Count']
                    # this.map_others[1] -= sgnl['Count']
                    # this.mapped[0] += sgnl['Count']
                    update_signals_frame()
                if 'Biological' in sgnl['Type']:
                    this.map_bio += sgnl['Count']
                    # this.map_others[1] -= sgnl['Count']
                    # this.mapped[0] += sgnl['Count']
                    update_signals_frame()
                    
    if entry['event'] == 'SAASignalsFound':
        update = False
        if 'Signals' in entry:
            for sgnl in entry['Signals']:
                this.map_signals += sgnl['Count']
                update = True
                # on détermine le type et le count
                # if 'Guardian' in sgnl['Type']:
                #     this.map_signals += sgnl['Count']
                #     update_signals_frame()
                # if 'Thargoid' in sgnl['Type']:
                #     this.map_signals += sgnl['Count']
                #     update_signals_frame()
                
        if update:
            update_signals_frame()
        