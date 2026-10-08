"""
Falsk Live-sang med spor, solo, rack-makroer og volum.

Listenere kalles synkront når en verdi settes, og Parameter kaster ved verdier utenfor
[min, max] slik Live gjør, så klampefeil i scriptet blir synlige.
"""


class _Listenable:

    def __init__(self):
        self._listeners = {}

    def _add(self, name, fn):
        self._listeners.setdefault(name, []).append(fn)

    def _remove(self, name, fn):
        # Live kaster også når listeneren ikke er registrert.
        self._listeners.get(name, []).remove(fn)

    def _notify(self, name):
        for fn in list(self._listeners.get(name, [])):
            fn()


class Parameter:

    def __init__(self, name, min=0.0, max=1.0, value=0.0):
        self.name = name
        self.min = min
        self.max = max
        self._value = value
        self.default_value = value  # det dobbeltklikk i Live setter parameteren til

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        if not self.min <= v <= self.max:
            raise RuntimeError('Invalid value %r for %s (range %r-%r)' % (v, self.name, self.min, self.max))
        self._value = v


class Device:

    def __init__(self, name, class_name, parameters):
        self.name = name
        self.class_name = class_name
        self.parameters = parameters
        # Makro-variasjoner (bare rack har dem i Live): hver er en liste med makroverdier.
        self._variations = []
        self.selected_variation_index = -1

    @property
    def variation_count(self):
        return len(self._variations)

    def store_variation(self):
        self._variations.append([p.value for p in self.parameters[1:]])
        self.selected_variation_index = len(self._variations) - 1

    def recall_selected_variation(self):
        for param, value in zip(self.parameters[1:], self._variations[self.selected_variation_index]):
            param.value = value


def audio_effect_rack(name='Audio Effect Rack'):
    # parameters[0] er av/på, 1-16 er makroene (område 0-127).
    params = [Parameter('Device On', 0, 1, 1)]
    params += [Parameter('Macro %d' % i, 0, 127, 0) for i in range(1, 17)]
    return Device(name, 'AudioEffectGroupDevice', params)


def plain_device(name='EQ Eight', class_name='Eq8'):
    return Device(name, class_name, [Parameter('Device On', 0, 1, 1)])


class _MixerDevice:

    def __init__(self, n_sends):
        self.volume = Parameter('Track Volume', 0.0, 1.0, 0.85)
        self.sends = [Parameter('Send %s' % 'AB'[i], 0.0, 1.0, 0.0) for i in range(n_sends)]


class Track(_Listenable):

    def __init__(self, name, devices=None):
        _Listenable.__init__(self)
        self.name = name
        self.devices = devices or []
        self.mixer_device = _MixerDevice(n_sends=2)
        self._solo = False

    @property
    def solo(self):
        return self._solo

    @solo.setter
    def solo(self, value):
        if value != self._solo:
            self._solo = value
            self._notify('solo')

    def add_solo_listener(self, fn):
        self._add('solo', fn)

    def remove_solo_listener(self, fn):
        self._remove('solo', fn)


class MasterTrack:
    """Master har ikke solo i Live."""

    def __init__(self):
        self.name = 'Master'
        self.devices = []
        self.mixer_device = _MixerDevice(n_sends=0)


class _SongView(_Listenable):

    def __init__(self, initial):
        _Listenable.__init__(self)
        self._selected = initial

    @property
    def selected_track(self):
        return self._selected

    @selected_track.setter
    def selected_track(self, track):
        if track is not self._selected:
            self._selected = track
            self._notify('selected_track')

    def add_selected_track_listener(self, fn):
        self._add('selected_track', fn)

    def remove_selected_track_listener(self, fn):
        self._remove('selected_track', fn)


class CuePoint:
    """En markør (locator) i arrangementet."""

    def __init__(self, song, name, time):
        self._song = song
        self.name = name
        self.time = time

    def jump(self):
        self._song.current_song_time = self.time
        self._song._continue_from = self.time


class Song(_Listenable):

    def __init__(self, tracks):
        _Listenable.__init__(self)
        self._tracks = list(tracks)
        self.cue_points = ()
        self.is_playing = False
        # Transporten slik brukeren har sett den oppføre seg i Live (se SIGNALS.md):
        #   _time           nåla, det current_song_time viser
        #   _insert         der start_playing() spiller fra. jump_by() i stillstand regner herfra.
        #   _continue_from  der continue_playing() tar opp igjen: stedet låta ble stoppet
        self._time = 0.0
        self._insert = 0.0
        self._continue_from = None
        self.loop_start = 0.0
        self.master_track = MasterTrack()
        self.view = _SongView(self._tracks[0] if self._tracks else self.master_track)

    @property
    def tracks(self):
        return tuple(self._tracks)

    def add_tracks_listener(self, fn):
        self._add('tracks', fn)

    def remove_tracks_listener(self, fn):
        self._remove('tracks', fn)

    @property
    def current_song_time(self):
        return self._time

    @current_song_time.setter
    def current_song_time(self, time):
        if time < 0:
            raise RuntimeError('Invalid song time %r' % time)
        self._time = time
        if not self.is_playing:
            self._insert = time      # i stillstand flytter dette også startpunktet

    def continue_playing(self):
        if self._continue_from is not None:
            self._time = self._continue_from
        self.is_playing = True

    def start_playing(self):
        self._time = self._insert
        self.is_playing = True

    def stop_playing(self):
        self.is_playing = False
        self._continue_from = self._time

    def jump_by(self, beats):
        if self.is_playing:
            self.current_song_time = self._time + beats
        else:
            self.current_song_time = self._insert + beats

    # Hjelpere for å simulere endringer gjort i Live-UI-et.

    def add_marker(self, name, time):
        # Live holder ikke lista sortert på tid, så nye markører legges bare bakerst.
        self.cue_points += (CuePoint(self, name, time),)

    def create_track(self, name=None, devices=None):
        track = Track(name or 'Spor %d' % (len(self._tracks) + 1), devices)
        self._tracks.append(track)
        self._notify('tracks')
        return track

    def delete_track(self, index):
        track = self._tracks.pop(index)
        if self.view.selected_track is track:
            self.view.selected_track = self._tracks[min(index, len(self._tracks) - 1)] if self._tracks else self.master_track
        self._notify('tracks')


def default_song(n_tracks=20):
    """20 spor gir to sider. Spor 1-3 har rack, spor 4 har rack bak en EQ, resten ingen."""
    tracks = []
    for i in range(1, n_tracks + 1):
        if i <= 3:
            devices = [audio_effect_rack('Rack %d' % i)]
        elif i == 4:
            devices = [plain_device(), audio_effect_rack('Rack 4')]
        else:
            devices = []
        tracks.append(Track('Spor %d' % i, devices))
    return Song(tracks)
