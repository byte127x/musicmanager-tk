'''
MusicManager *Tk*
Unlike most tkinter music players, this app seeks to also catalog your music apps, and play a wide variety of music formats (achieved using libvlc)

Created by: byte127x/GL32
Other programmers are mentioned where they contrbuted
'''

# GUI Imports (CTkMenuBar, CTkListBox, and CTkTable are made by Akascape)
import customtkinter as ctk
from lib.CTkMenuBar import *
from tkinter import DoubleVar, filedialog
from CTkListbox import CTkListbox
from CTkTable import CTkTable

# Non-Graphical Imports
import json, os, platform, vlc, time, music_tag, random, string
from functools import partial
from PIL import Image, ImageTk
from threading import Thread, Event

# Adds libvlc DLLs (Windows)
os.add_dll_directory(os.getcwd()+'/lib/libvlc')

# auto-fit in css but in tkinter ig
class AutoGrid(ctk.CTkFrame):
	# Original code comes from Novel (https://stackoverflow.com/a/47705166/17596528)
	def __init__(self, master=None, **kwargs):
		super().__init__(master, **kwargs)
		self.columns = None
		self.gridding = False
		self.bind('<Configure>', self.regrid)

	def regrid(self, event=None):
		if self.gridding:
			return
		width = self.winfo_width()
		children = self.winfo_children()
		max_width = 190
		cols = width // max_width
		if cols == self.columns: # if the column number has not changed, abort
			return
		self.gridding = True
		rows = 0
		for i, child in enumerate(children):
			try:
				assigned_row = i//cols
			except ZeroDivisionError:
				assigned_row = 0
			try:
				assigned_col = i%cols
			except ZeroDivisionError:
				assigned_col = 0
			if assigned_row > rows:
				rows = assigned_row
			self.grid_columnconfigure(i, weight=0)
			if rows == 0:
				self.grid_columnconfigure(i, weight=1)
			child.grid_forget()
			child.grid(row=assigned_row, column=assigned_col, sticky='nsew', padx=5, pady=5, ipady=5)
		self.columns = cols
		self.gridding = False

class Timer(Thread):
	"""
	A class serving same function as wxTimer... but there may be better ways to do this
	(from VideoLan Example)
	"""
	def __init__(self, callback, tick):
		Thread.__init__(self)
		self.callback = callback
		self.stopFlag = Event()
		self.tick = tick
		self.iters = 0

	def run(self):
		while not self.stopFlag.wait(self.tick):
			self.iters += 1
			self.callback()

	def stop(self):
		self.stopFlag.set()

	def get(self):
		return self.iters

class Queue:
	# Based off of the tkinter vlc example from VideoLan (http://git.videolan.org/?p=vlc/bindings/python.git;a=blob;f=examples/tkvlc.py;h=55314cab09948fc2b7c84f14a76c6d1a7cbba127;hb=HEAD)
	def __init__(self, library=None, parent=None):
		self.parent = parent
		self.tracklist = []
		self.index = 0
		self.library = library
		self.paused = True

		# VLC Stuff
		self.instance = vlc.Instance()
		self.player = self.instance.media_player_new()

		self.timer = Timer(self.on_timer, 1.0)
		self.timer.start()
		self.parent.update()

		# Video player Widget
		self.vidplayer = ctk.CTkToplevel(self.parent)
		self.vidplayer.title('Video Media Player (LibVLC)')
		self.vidplayer.withdraw()

	# GUI Bindings
	def bind_to_time_controller(self, timeslider):
		self.scale_var = DoubleVar()
		timeslider.configure(variable=self.scale_var, command=self.scale_sel, from_=0, to=1000)
		self.timeslider = timeslider
		self.timeslider_last_val = ""
		self.timeslider_last_update = time.time()

	def _quit(self):
		print("_quit: bye")
		root = ctk.CTk()
		root.quit()     # stops mainloop
		root.destroy()  # this is necessary on Windows to prevent "Fatal Python Error: PyEval_RestoreThread: NULL tstate"
		os._exit(1)

	def exit(self):
		''' Exits the Video Player Safely '''
		self.Close()

	# Media Playback
	def open(self, path):
		''' Opens video on specified 'path' variable '''
		self.parent.update_queue_viewer()
		self.parent.update_lyrics_viewer()
		self.timeslider.set(0)
		if os.path.isfile(path):
			dirname = os.path.dirname(path)
			filename = os.path.basename(path)

			self.media = self.instance.media_new(str(os.path.join(dirname, filename)))
			self.player.set_media(self.media)

			song_details = self.parent.library['Songs'][self.tracklist[self.index]]
			try:
				img_pil = Image.open(self.parent.library['Albums'][song_details['album']]['album_art'])
				image = ctk.CTkImage(img_pil, size=(70, 70))
			except KeyError:
				image = self.parent.image('music', (70, 70))
			except FileNotFoundError:
				image = self.parent.image('music', (70, 70))
			self.parent.album_labelview.configure(text=self.parent.library['Albums'][song_details['album']]['name'])
			self.parent.artist_labelview.configure(text=self.parent.library['Artists'][song_details['artist']]['name'])
			self.parent.albumart_labelview.configure(image=image)

			if path == self.parent.fnf_sound:
				self.parent.song_labelview.configure(text='{File Not Found} - '+song_details['title'])
			else:
				self.parent.song_labelview.configure(text=song_details['title'])

			# video checker
			if path.split('.')[-1] in ['mp4', 'wmv', 'avi', 'mov', 'mkv', 'amv', 'flv', 'webm', 'ogv', 'gif', 'asf', 'mpg', 'mpeg', 'm2v', 'm4v', '3gp', '3gpp', 'f4v']:
				self.vidplayer.deiconify()
				if platform.system() == 'Windows':
					self.player.set_hwnd(self.vidplayer.winfo_id())
				else:
					self.player.set_xwindow(self.vidplayer.winfo_id())
				self.vidplayer.attributes('-topmost', 1)
				self.vidplayer.attributes('-topmost', 0)
			else:
				self.vidplayer.withdraw()
				if platform.system() == 'Windows':
					self.player.set_hwnd(self.parent.winfo_id())
				else:
					self.player.set_xwindow(self.parent.winfo_id())
			self.play()

			try:
				self.volslider.set(self.player.audio_get_volume())
			except:
				return
		else:
			self.open(self.parent.fnf_sound)

	def play(self):
		self.paused = False
		if not self.player.get_media():
			self.open(self.parent.library['Songs'][self.tracklist[self.index]]['file_path'])
		else:
			if self.player.play() == -1:
				self.errorDialog("Unable to play.")

			'''
			if (not self.player.is_playing()) and (self.player.get_length() > 100):
				self.open(self.parent.library['Songs'][self.tracklist[self.index]]['file_path'])
				self.timeslider.set(0)
			'''

	def pause(self):
		self.player.pause()
		self.paused = True

	def stop(self):
		self.player.stop()
		self.timeslider.set(0)

	# Next/Previous
	def next(self):
		self.index += 1
		if self.index >= len(self.tracklist):
			self.index -= 1
		self.open(self.parent.library['Songs'][self.tracklist[self.index]]['file_path'])
		self.play()

	def prev(self):
		self.index -= 1
		if self.index <= 0:
			self.index = 0

		self.open(self.parent.library['Songs'][self.tracklist[self.index]]['file_path'])
		self.play()

	# Boring Timer Stuff
	def on_timer(self):
		if (not self.player.is_playing()) and (not self.paused):
			if not self.index == len(self.tracklist)-1:
				self.next()
			return
		if self.player == None:
			return

		length = self.player.get_length()
		dbl = length * 0.001
		try:
			self.timeslider.configure(to=dbl)
		except:
			return

		tyme = self.player.get_time()
		if tyme == -1:
			tyme = 0
		dbl = tyme * 0.001
		self.timeslider_last_val = ("%.0f" % dbl) + ".0"

		if time.time() > (self.timeslider_last_update + 2.0):
			self.timeslider.set(dbl)

	def scale_sel(self, evt):
		if self.player == None:
			return
		nval = self.scale_var.get()
		sval = str(nval)
		if self.timeslider_last_val != sval:
			self.timeslider_last_update = time.time()
			mval = "%.0f" % (nval * 1000)
			self.player.set_time(int(mval))

	# Actual Queue/Playlist Stuff
	def get_current_song(self):
		return self.library["Songs"][self.tracklist[index]]

	def add_to_queue(self, adds):
		if type(adds) == int:
			self.tracklist.append(adds)
		else:
			for song in adds:
				self.tracklist.append(song)

class App(ctk.CTk):
	def __init__(self):
		# Load App Settings
		with open('data/settings.json') as file:
			settings = json.loads(file.read())
			self.theme = settings['theme']
			self.mode = settings['mode']
		ctk.set_default_color_theme(self.theme)
		ctk.set_appearance_mode(self.mode)
		self.fnf_sound = 'lib/filenotfound.wav'

		# Initialize the Window
		super().__init__()
		self.title('MusicManager *Tk*')
		self.geometry('1500x770')
		self.minsize(250, 250)
		self.images = {}
		self.iconbitmap('lib/icon.ico')
		self.playlist_viewer = None
		self.lyrics_window = None
		self.lyrics_textbox = None

		# Grid Configures
		self.grid_rowconfigure(0, weight=1)
		self.grid_columnconfigure(0, weight=1)

		# Load Music Library and Queue
		with open('data/library.json', encoding='utf8') as file:
			self.library = json.loads(file.read())
		self.queue = Queue(library=self.library, parent=self)
		self.queue.add_to_queue([])
		self.protocol("WM_DELETE_WINDOW", self.queue._quit)

		# Load Music Player GUI
		# Music Info
		self.player = ctk.CTkFrame(self, height=90)
		self.player.grid(row=1, column=0, sticky='ew', padx=10, pady=(0, 10))
		self.player.grid_propagate(False)
		self.player.grid_rowconfigure(0, weight=1)
		self.player.grid_columnconfigure(2, weight=1)

		info_frame = ctk.CTkFrame(self.player, fg_color='transparent')
		info_frame.grid_rowconfigure(1, weight=1)
		info_frame.grid(row=0, column=1, padx=10, pady=10, sticky='nsew')
		self.albumart_labelview = ctk.CTkLabel(self.player, text='', image=self.image('music', (70, 70)))
		self.albumart_labelview.grid(row=0, column=0, padx=10, pady=10)

		self.song_labelview = ctk.CTkLabel(info_frame, text='Untitled', font=('Louis George Cafe', 18))
		self.artist_labelview = ctk.CTkLabel(info_frame, text='Unknown Artist', font=(None, 14))
		self.album_labelview = ctk.CTkLabel(info_frame, text='Unknown Album', font=(None, 14))
		self.song_labelview.grid(row=0, column=0, sticky='nsew')
		self.artist_labelview.grid(row=1, column=0, sticky='nsew')
		self.album_labelview.grid(row=2, column=0, sticky='nsew')

		# Music Controls
		controls_frame = ctk.CTkFrame(self.player, fg_color='transparent')
		controls_frame.grid(row=0, column=2, padx=10, pady=10, sticky='nsew')
		controls_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
		controls_frame.grid_rowconfigure((0, 1), weight=1)
		slider = ctk.CTkSlider(controls_frame, from_=0, to=2, corner_radius=5)
		slider.grid(row=0, column=0, columnspan=4, sticky='ew')
		self.queue.bind_to_time_controller(slider)

		if self.mode == 'light':
			btn_clr = self.player.cget('fg_color')[0]
		else:
			btn_clr = self.player.cget('fg_color')[1]
		print(btn_clr)
		ctk.CTkButton(controls_frame, fg_color=btn_clr, image=self.image('ico_prev', (20, 20)), text='', font=(None, 16), command=self.queue.prev).grid(row=1, column=0, sticky='ew', padx=10)
		ctk.CTkButton(controls_frame, fg_color=btn_clr, image=self.image('ico_play', (20, 20)), text='', font=(None, 16), command=self.queue.play).grid(row=1, column=1, sticky='ew', padx=10)
		ctk.CTkButton(controls_frame, fg_color=btn_clr, image=self.image('ico_pause', (20, 20)), text='', font=(None, 16), command=self.queue.pause).grid(row=1, column=2, sticky='ew', padx=10)
		ctk.CTkButton(controls_frame, fg_color=btn_clr, image=self.image('ico_next', (20, 20)), text='', font=(None, 16), command=self.queue.next).grid(row=1, column=3, sticky='ew', padx=10)

		# Queue Viewer/Searchbox
		extras_frame = ctk.CTkFrame(self.player, fg_color='transparent')
		extras_frame.grid(row=0, column=3, padx=10, pady=10, sticky='nsew')
		extras_frame.grid_rowconfigure((0, 1), weight=1)
		extras_frame.grid_columnconfigure(0, weight=1)
		ctk.CTkButton(extras_frame, fg_color=btn_clr, image=self.image('ico_queue', (18, 18)), text='', font=(None, 16), command=self.queue_viewer, width=1).grid(row=0, column=0, sticky='ew', padx=10)
		ctk.CTkButton(extras_frame, fg_color=btn_clr, text='Lyrics', font=(None, 14), command=self.lyrics_viewer, width=1).grid(row=0, column=1, sticky='ew', padx=10)
		self.search = ctk.CTkEntry(extras_frame, placeholder_text='Search ...', font=(None, 14))
		self.search.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10)

		# Load Catalog Viewer
		self.catalog = ctk.CTkTabview(self)
		cat_albums = self.catalog.add('Albums')
		self.catalog_frame_artists = self.catalog.add('Artists')
		self.catalog_frame_genres = self.catalog.add('Genres')
		cat_songs = self.catalog.add('Songs')

		cat_scroller = ctk.CTkScrollableFrame(cat_albums, fg_color='transparent')
		cat_scroller.pack(fill='both', expand=1)
		self.catalog_frame_songs = ctk.CTkScrollableFrame(cat_songs, fg_color='transparent')
		self.catalog_frame_songs.pack(fill='both', expand=1)

		self.catalog_frame_albums = AutoGrid(cat_scroller, fg_color='transparent')
		self.catalog_frame_albums.pack(fill='both', expand=1)
		self.catalog.grid(row=0, column=0, sticky='nwes', padx=10, pady=(0, 10))

		self.build_catalog_ui()

		# Title Menu
		self.menu = CTkTitleMenu(self)
		self.file_menu = self.menu.add_cascade('File')
		self.file_dropdown = CustomDropdownMenu(widget=self.file_menu)
		self.file_dropdown.add_option(option='Import File', command=self.import_file)
		self.file_dropdown.add_option(option='Import Files', command=lambda: self.import_file(None, True))
		self.file_dropdown.add_option(option='Import Folder', command=self.import_folder)

		self.settings_menu = self.menu.add_cascade('Settings')
		self.settings_dropdown = CustomDropdownMenu(widget=self.settings_menu)

		self.settings_theme = self.settings_dropdown.add_submenu('Change Theme >')
		self.settings_theme.add_option(option='Blue (default)', command=lambda: self.change_theme('blue'))
		self.settings_theme.add_option(option='Green', command=lambda: self.change_theme('green'))
		self.settings_theme.add_option(option='Red', command=lambda: self.change_theme('lib/red.json'))

		self.settings_bright = self.settings_dropdown.add_submenu('Dark/Light Mode >')
		self.settings_bright.add_option(option='Dark', command=lambda: self.change_mode('dark'))
		self.settings_bright.add_option(option='Light', command=lambda: self.change_mode('light'))

	def lyrics_viewer(self):
		try:
			song = self.library['Songs'][self.queue.tracklist[self.queue.index]]
		except IndexError:
			return
		if self.lyrics_window is None:
			self.lyrics_window = ctk.CTkToplevel()
			self.lyrics_window.protocol('WM_DELETE_WINDOW', lambda *args: self.lyrics_window.withdraw())
			self.lyrics_window.title(f'Lyrics - {song["title"]}')

			ctk.CTkLabel(self.lyrics_window, text=f'Lyrics: "{song["title"]}"', font=(None, 18)).pack(pady=5)
			self.lyrics_textbox = ctk.CTkTextbox(self.lyrics_window, fg_color='transparent')
			self.lyrics_textbox.pack(pady=5, padx=5, fill='both', expand=1)
			try:
				lyrics = str(song['lyrics'])
			except KeyError:
				lyrics = 'No Lyrics Found'

			self.lyrics_textbox.insert('1.0', lyrics)
			self.lyrics_textbox.configure(state='disabled')
		else:
			self.lyrics_window.deiconify()

	def update_lyrics_viewer(self):
		if self.lyrics_window == None:
			return
		self.lyrics_textbox.destroy()
		self.lyrics_textbox = ctk.CTkTextbox(self.lyrics_window, fg_color='transparent')
		self.lyrics_textbox.pack(pady=5, padx=5, fill='both', expand=1)

		song = self.library['Songs'][self.queue.tracklist[self.queue.index]]
		try:
			lyrics = str(song['lyrics'])
		except KeyError:
			lyrics = 'No Lyrics Found'
		self.lyrics_textbox.insert('1.0', lyrics)

	def import_folder(self):
		em_pee_threes = filedialog.askdirectory()
		for root, dirs, files in os.walk(em_pee_threes):
			for file in files:
				self.import_file(root+'\\'+file)

	def import_file(self, path=None, multiple=False):
		if multiple:
			paths = filedialog.askopenfilenames(filetypes=(('MPEG-3 Audio', '*.mp3'), ('WAV Audio', '*.wav'), ('FLAC Audio', '*.flac'), ('OGG Audio', '*.ogg'), ('M4A Audio', '*.m4a'), ('AAC Audio', '*.aac'), ('AIFF Audio', '*.aif')))
			for path in paths:
				self.import_file(path, False)
			return
		else:
			if path == None:
				path = filedialog.askopenfilename(filetypes=(('MPEG-3 Audio', '*.mp3'), ('WAV Audio', '*.wav'), ('FLAC Audio', '*.flac'), ('OGG Audio', '*.ogg'), ('M4A Audio', '*.m4a'), ('AAC Audio', '*.aac'), ('AIFF Audio', '*.aif')))
		if path == '':
			return
		elif not (path.split('.')[-1] in ('mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac', 'aif')):
			return
		metadata = music_tag.load_file(path)
		song_object = {'file_path': path, 'loved': False, 'tracknum': int(metadata['tracknumber'])}

		# Lyrics
		if str(metadata['lyrics']) != '':
			song_object['lyrics'] = str(metadata['lyrics'])

		ar = None
		al = None
		title = 'Untitled Track'

		unknown_artist_id = None
		unknown_album_id = None

		# Look if the song's artist and album already exist
		for id, artist in enumerate(self.library['Artists']):
			if artist['name'] == str(metadata['albumartist']):
				ar = id
		for id, album in enumerate(self.library['Albums']):
			print(f'''
				{str(metadata['albumartist'])}
				vs.
				{self.library['Artists'][album['artist']]['name']}

			''')
			if (album['name'] == str(metadata['album'])) and (self.library['Artists'][album['artist']]['name'] == str(metadata['albumartist'])):
				print('Matched')
				al = id

		if str(metadata['tracktitle']) == '':
			song_object['title'] = 'Untitled Track'
		else:
			song_object['title'] = str(metadata['tracktitle'])

		# Adds the artist if it doesn't exist
		if ar == None:
			# Unknown Artist
			if str(metadata['albumartist']) == '':
				# Checks for an unknown artist
				for id, artist in enumerate(self.library['Artists']):
					if artist['name'] == "Unknown Artist":
						unknown_artist_id = id
				if unknown_artist_id is None:
					ar = len(self.library['Artists'])
					self.library['Artists'].append(
						{"name": "Unknown Artist", "discography": []},
					)
				else:
					ar = unknown_artist_id
			else:
				new_artist = {"name": str(metadata['albumartist']), "discography": []}
				new_artist_id = len(self.library['Artists'])
				self.library['Artists'].append(new_artist)
				ar = new_artist_id

		# Adds the artist to the song object
		song_object['artist'] = ar

		# Adds the album if it doesn't exist
		if al == None:
			# Unknown Artist
			if str(metadata['album']) == '':
				# Checks for an unknown artist
				for id, album in enumerate(self.library['Albums']):
					if album['name'] == "Unknown Album":
						unknown_album_id = id
				if unknown_album_id is None:
					al = len(self.library['Albums'])
					self.library['Albums'].append(
						{"name": "Unknown Album", "artist": ar, "year": 1900, "genre": "N/A", "tracklist": []}
					)
				else:
					al = unknown_album_id
			else:
				new_album = {"name": str(metadata['album']), "artist": ar, "year": int(metadata['year']), "genre": str(metadata['genre']), "tracklist": []}
				new_album_id = len(self.library['Albums'])
				self.library['Albums'].append(new_album)
				al = new_album_id

		# Adds the album to the song object
		song_object['album'] = al
		if not (al in self.library['Artists'][ar]['discography']):
			self.library['Artists'][ar]['discography'].append(al)
		self.library['Albums'][al]['tracklist'].append(len(self.library['Songs']))

		# Album Art!
		has_albumart_already = True
		try:
			has_albumart_already = self.library['Albums'][al]['album_art']
		except KeyError:
			if metadata['artwork'].first != None:
				# Generate Random Filename
				filename = ''
				for x in range(25):
					filename += random.choice(string.ascii_lowercase)

				filetype = 'bmp'
				match str(metadata['artwork'].first.mime):
					case 'image/jpeg':
						filetype = 'jpg'
					case 'image/gif':
						filetype = 'gif'
					case 'image/png':
						filetype = 'png'
					case 'image/webp':
						filetype = 'webp'
					case 'image/tiff':
						filetype = 'tif'

				# Write to file and add to album
				full_path = f'data/albumart/{filename}.{filetype}'
				with open(full_path, 'wb') as file:
					file.write(metadata['artwork'].first.data)
				self.library['Albums'][al]['album_art'] = full_path

		# Adds the final song object to the library
		self.library['Songs'].append(song_object)

		# Sorts song's album discography (TO AVOID JUMBLED SONG ORDER)
		self.library['Albums'][al]['tracklist'].sort(key=lambda d: self.library['Songs'][d]['tracknum'])

		# Flush to file
		print('Flusing')
		with open('data/library.json', 'w+') as file:
			file.write(json.dumps(self.library))
		print('Done!')

	def queue_viewer(self):
		if self.playlist_viewer is None:
			self.playlist_viewer = ctk.CTkToplevel(self)
			self.playlist_viewer.title('Queue')
			self.playlist_viewer.protocol('WM_DELETE_WINDOW', lambda *args: self.playlist_viewer.withdraw())
		else:
			self.playlist_viewer.deiconify()
		self.update_queue_viewer()

	def update_queue_viewer(self):
		if self.playlist_viewer is None:
			return
		for x in self.playlist_viewer.winfo_children():
			x.destroy()

		ctk.CTkLabel(self.playlist_viewer, text='Current Queue:', font=(None, 20)).pack(pady=(5, 0))
		table_values = []
		for place, song_id in enumerate(self.queue.tracklist):
			if self.queue.index == place:
				first_col = '▶|'
			else:
				first_col = place+1
			table_values.append([first_col, self.library['Songs'][song_id]['title']])
		t = CTkTable(self.playlist_viewer, column=2, values=table_values, colors=['gray15', 'gray20'])
		t.pack(pady=5, padx=5, fill='both', expand=1)

	def build_catalog_ui(self):
		# Builds all of the Albums and Artists and stuff

		# Album UI
		for idx, album in enumerate(self.library['Albums']):
			try:
				try:
					img_pil = Image.open(album['album_art'])
					image = ctk.CTkImage(img_pil, size=(175, 175))
				except FileNotFoundError:
					image = self.image('music', (175, 175))
			except KeyError:
				image = self.image('music', (175, 175))
			ctk.CTkButton(self.catalog_frame_albums, text=f'{album["name"]}\n{self.library["Artists"][album["artist"]]["name"]}', command=partial(self.album_popup, album, idx), compound='top', image=image, width=175).grid(row=0, column=idx, sticky='nwes')

		# Artists UI
		self.catalog_frame_artists.grid_columnconfigure(0, weight=3)
		self.catalog_frame_artists.grid_columnconfigure(1, weight=10)
		self.catalog_frame_artists.grid_rowconfigure(0, weight=1)
		if self.mode == 'light':
			lb_text_clr = self.cget('fg_color')[1]
		else:
			lb_text_clr = self.cget('fg_color')[0]
		artists_lb = CTkListbox(self.catalog_frame_artists, text_color=lb_text_clr, command=lambda *args: self.change_artist_view(artists_lb), width=10)
		artists_lb.grid(row=0, column=0, sticky='nsew')
		self.album_container = ctk.CTkScrollableFrame(self.catalog_frame_artists)
		self.album_container.grid(row=0, column=1, sticky='nsew', pady=0, padx=0)
		self.artists_album_container = AutoGrid(self.album_container, fg_color='transparent')
		self.artists_album_container.pack(fill='both', expand=1, pady=0, padx=0)

		self.sorted_artists = self.library['Artists'].copy()
		self.sorted_artists.sort(key=lambda d: d['name'])
		for artist in self.sorted_artists:
			artists_lb.insert('END', artist['name'])


		# Songs UI
		table = [
			['Title', 'Artist', 'Album', 'Year', '❤']
		]
		# Song Sorter
		for song in self.library['Songs']:
			line = []
			line.append(song['title'])
			line.append(self.library['Artists'][song['artist']]['name'])
			line.append(self.library['Albums'][song['album']]['name'])
			line.append(self.library['Albums'][song['album']]['year'])
			line.append(song['loved'])
			table.append(line)
		self.catalog_frame_songs.grid_columnconfigure(0, weight=1)
		if self.mode == 'light':
			table_colors = ['#dedede', '#cccccc']
		else:
			table_colors = ['gray15', 'gray20']
		CTkTable(self.catalog_frame_songs, column=5, values=table, colors=table_colors).grid(row=0, column=0, sticky='ew')

	def change_artist_view(self, lb):
		self.artists_album_container.destroy()
		self.artists_album_container = AutoGrid(self.album_container, fg_color='transparent')
		self.artists_album_container.pack(fill='both', expand=1, pady=0, padx=0)
		for idx, album_id in enumerate(self.sorted_artists[lb.curselection()]['discography']):
			album = self.library['Albums'][album_id]
			try:
				img_pil = Image.open(album['album_art'])
				image = ctk.CTkImage(img_pil, size=(175, 175))
			except KeyError:
				image = self.image('music', (175, 175))
			except FileNotFoundError:
				image = self.image('music', (175, 175))
			ctk.CTkButton(self.artists_album_container, text=f'{album["name"]}\n{self.library["Artists"][album["artist"]]["name"]}', command=partial(self.album_popup, album, idx), compound='top', image=image, width=175).grid(row=0, column=idx, sticky='nwes')

	def image(self, name, size=None):
		# Gets an image from the default image library
		img = Image.open(f'lib/img/{name}.png')
		if size == None:
			size = (img.width, img.height)
		self.images[name] = ctk.CTkImage(img, size=size)
		return self.images[name]

	def album_popup(self, album, index):
		popup = ctk.CTkToplevel()
		popup.title(f'Album: {album["name"]}')

		try:
			img_pil = Image.open(album['album_art'])
			image = ctk.CTkImage(img_pil, size=(175, 175))
		except KeyError:
			image = self.image('music', (175, 175))
		except FileNotFoundError:
			image = self.image('music', (175, 175))
		album_art = ctk.CTkLabel(popup, image=image, text='')
		album_art.grid(row=0, column=0, padx=5, pady=5)
		popup.grid_columnconfigure(1, weight=1)
		popup.grid_rowconfigure(0, weight=0)
		popup.grid_rowconfigure(1, weight=1)

		info_frame = ctk.CTkFrame(popup, height=175, width=200, corner_radius=0)
		info_frame.grid_columnconfigure(0, weight=1)
		info_frame.grid_rowconfigure(0, weight=5)
		info_frame.grid_rowconfigure((1, 2 ,3), weight=4)
		info_frame.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
		info_frame.grid_propagate(False)

		album_title = ctk.CTkLabel(info_frame, justify='left', text=album["name"], font=(None, 24), wraplength=500)
		album_title.grid(row=0, column=0, pady=(8, 2), padx=5)
		ctk.CTkLabel(info_frame, justify='left', text=self.library["Artists"][album["artist"]]["name"], font=(None, 17)).grid(row=1, column=0, padx=5)
		ctk.CTkLabel(info_frame, justify='left', text=album["genre"], font=(None, 16)).grid(row=2, column=0, padx=5)
		ctk.CTkLabel(info_frame, justify='left', text=album["year"], font=(None, 16)).grid(row=3, column=0, padx=5)

		lb = CTkListbox(popup)
		if self.mode == 'light':
			lb.configure(text_color='gray10')
		lb.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=5, pady=5)
		lb_internals = []
		for song_id in album['tracklist']:
			song = self.library['Songs'][song_id]
			lb_internals.append(song_id)
			tracknum = song['tracknum']
			if tracknum < 10:
				tracknum = f"0{song['tracknum']}"
			lb.insert('end', f"{tracknum}: {song['title']}")
		controls = ctk.CTkFrame(popup, fg_color='transparent')
		ctk.CTkButton(controls, text='Add Selected to Queue', command=lambda: self.add_to_queue(lb_internals, lb.curselection())).pack(fill='x', padx=5, side='left')
		ctk.CTkButton(controls, text='Edit Album', command=lambda: self.album_edit(index)).pack(fill='x', padx=5, side='right')
		controls.grid(row=2, column=0, columnspan=2, sticky='nsew', padx=5, pady=5)

		#popup.bind('<Configure>', lambda e: self.resize_wraplen(info_frame, album_title))

	def edit_album_save(self, dlg, id, alb_name):
		self.dismiss_modal(dlg)

	def dismiss_modal(self, dlg):
		dlg.grab_release()
		dlg.destroy()

	def album_edit(self, index):
		dlg = ctk.CTkToplevel()
		dlg.title('Album Editor')
		dlg.grid_rowconfigure(9, weight=1)
		dlg.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(dlg, text='Album Index: '+str(index)).grid(row=0, column=0, columnspan=2)

		ctk.CTkLabel(dlg, text='Album Name: ').grid(row=1, column=0, sticky='ew', padx=5, pady=5)
		alb_name = ctk.CTkEntry(dlg, width=60)
		alb_name.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
		alb_name.insert(0, self.library['Albums'][index]['name'])

		ctk.CTkLabel(dlg, text='Genre: ').grid(row=2, column=0, sticky='ew', padx=5, pady=5)
		alb_name = ctk.CTkEntry(dlg, width=60)
		alb_name.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
		alb_name.insert(0, self.library['Albums'][index]['genre'])

		bottom_frame = ctk.CTkFrame(dlg, fg_color='transparent')
		bottom_frame.grid(row=10, column=0, columnspan=2, pady=5, sticky='ew')
		ctk.CTkButton(bottom_frame, text='Save', command=lambda: self.edit_album_save(dlg, index, alb_name.get())).pack(side='left')
		ctk.CTkButton(bottom_frame, text='Cancel', command=lambda: self.dismiss_modal(dlg)).pack(side='right')

		# Dialog code is from TkDocs (https://tkdocs.com/tutorial/windows.html)
		dlg.protocol("WM_DELETE_WINDOW", lambda: self.dismiss_modal(dlg)) # intercept close button
		dlg.transient(self)   # dialog window is related to main
		dlg.wait_visibility() # can't grab until window appears, so we wait
		dlg.grab_set()        # ensure all input goes to our window
		dlg.wait_window()
	
	def add_to_queue(self, list, index):
		if index != None:
			self.queue.add_to_queue(list[index])
			self.update_queue_viewer()

	# Menu Commands
	def change_theme(self, theme):
		# Changes the app's color theme
		self.destroy()
		with open('data/settings.json', 'w+') as file:
			file.write(json.dumps({
				"mode": self.mode,
				"theme": theme
			}))
		ctk.set_default_color_theme(theme)
		root = App()
		root.mainloop()

	def change_mode(self, mode):
		# Changes the app to light or dark mode
		self.destroy()
		with open('data/settings.json', 'w+') as file:
			file.write(json.dumps({
				"mode": mode,
				"theme": self.theme
			}))
		ctk.set_appearance_mode(mode)
		root = App()
		root.mainloop()

if __name__ == '__main__':
	root = App()
	root.mainloop()