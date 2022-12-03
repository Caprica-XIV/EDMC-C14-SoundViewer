# EDMC-C14-SoundViewer
EDMC plugin to display sound wave and spectrogram into EDMC window.

Requirements and functionnalities
---
This plugin works with a server executable (included) compiled for Windows 64bits only.
For linux releases, you will need to compile a linux version of the [webservice](https://github.com/Caprica-XIV/C14-webservice).

The software records EVERY sound emited from the device of your choosing and display the according wave form into the frame of EDMC. If you want to check this new thargoid probe sound you just acquire, you might want to stop any music, speech and other sounds that will change your reading.

To record sound, you need a compatible soundcard. Most commonly your computer shall have a Realtek mixer input/ouput that needs to be enable in order to record (input) the sound from your speaker (output). Windows manage sound device through different APIs, usually the best way to acquire sound output from speaker is throught the WASAPI sound driver.

In some cases, your computer is not able to manage a sound card with output-to-input redirection. The best way to achieve this then is by using a virtual sound card to redirect signal. I recommand to check [vb-audio virtual cable](https://vb-audio.com/Cable/) app, you will need to assign this virtual card as default thou in order to record speaker output into EDMC.

Installation
---
Download from [latest release](https://github.com/Caprica-XIV/EDMC-C14-SoundViewer/releases/tag/1.0.0).
Extract zip files into the EDMC plugin folder.

Usage
---
Launch EDMC, press the "Start server" button when you wish to start recording, select a device in the list (mix of sound card input with API) and press the " > " button to launch the acquisition.
Press one of the three button below the view canvas to change the visualisation mode. Spectrogram needs extra seconds to be computed than others.

Troubleshoot
---
Try different sound card and API configurations. Wait 5 to 10 seconds after lauching a stream for signal acquisition, it is needed for caching data and responsiveness (is that a real word?).
Changing mode might refresh the stream when it crashed.
If server is defenitly down, restart EDMC.

The server uses port 5005, check that this is free of usage.

Disclaimer
--------
This software is provided as is, you might use it at your own risk.
By using this software you acknowledge that the writer shall not be responsible for any damages or consequences resulting of the uses of the software.

I'm learning Python and Git/Github with this, so bear with me!
You can contact me here or through [twitter](https://twitter.com/CmdrXiv) ;)

License
-------
This software is under the [MIT license](https://github.com/Caprica-XIV/EDMC-C14-SoundViewer/blob/main/LICENSE).
