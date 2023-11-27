

class RedeemTemplate:
    '''
    Templating class to give easier configuration of redeems
    '''
    redeem_type: str
    broadcaster_id:str
    title:str
    cost:int
    prompt:str
    is_enabled:bool=False
    background_color:str=None
    is_user_input_required:bool=False
    is_max_per_stream_enabled:bool=False
    max_per_stream:int=None
    is_max_per_user_per_stream_enabled:bool=False
    max_per_user_per_stream:int=None
    is_global_cooldown_enabled:bool=True
    global_cooldown_seconds:int=None
    should_redemptions_skip_request_queue:bool=True
    
    def __init__(self, redeem_type: str,
                title:str,
                cost:int,
                prompt:str,
                broadcaster_id:str = None,
                is_enabled:bool=False,
                background_color:str=None,
                is_user_input_required:bool=False,
                is_max_per_stream_enabled:bool=False,
                max_per_stream:int=None,
                is_max_per_user_per_stream_enabled:bool=False,
                max_per_user_per_stream:int=None,
                is_global_cooldown_enabled:bool=True,
                global_cooldown_seconds:int=None,
                should_redemptions_skip_request_queue:bool=True) -> None:
        
        self.redeem_type = redeem_type
        self.broadcaster_id = broadcaster_id
        self.title = title
        self.cost = cost
        self.prompt = prompt
        self.is_enabled = is_enabled
        self.background_color = background_color
        self.is_user_input_required = is_user_input_required
        self.is_max_per_stream_enabled = is_max_per_stream_enabled
        self.max_per_stream = max_per_stream
        self.is_max_per_user_per_stream_enabled = is_max_per_user_per_stream_enabled
        self.max_per_user_per_stream = max_per_user_per_stream
        self.is_global_cooldown_enabled = is_global_cooldown_enabled
        self.global_cooldown_seconds = global_cooldown_seconds
        self.should_redemptions_skip_request_queue = should_redemptions_skip_request_queue
    
    
    
    
        
        

class Redeem_Builder:
    '''
    Class to build an array of redeems based on certain standards
    Currently usable redeems:
    HEAL,
    KILL,
    SWAP,
    REVEAL,
    ZOOMIES,
    GLASS,
    FREEZE,
    BLEED,
    TRUNTABLES,
    MEELEE, 
    DEFAULT
    '''
    
    redeems_temps: [RedeemTemplate]
    
    
    
    
    
    def __init__(self) -> None:
        self.redeems_temps = []
        kill = RedeemTemplate(
        redeem_type = 'kill',
        title = 'Kill | Twitch2BBR',
        prompt = 'Kills the streamer',
        cost = 1000,
        is_global_cooldown_enabled = True,
        global_cooldown_seconds = 300
        )
        self.redeems_temps.append(kill)
        
        heal = RedeemTemplate(
        redeem_type = 'heal',
        title = 'Heal | Twitch2BBR',
        prompt = 'Heals the streamer',
        cost = 500,
        is_global_cooldown_enabled = True,
        global_cooldown_seconds = 60
        )
        self.redeems_temps.append(heal)
        
        swap = RedeemTemplate(
        redeem_type = 'swap',
        title = 'Swap | Twitch2BBR',
        prompt = 'Swaps the streamer with a random player',
        cost = 500,
        is_global_cooldown_enabled = True,
        global_cooldown_seconds = 60
        )
        self.redeems_temps.append(swap)
        
        reveal = RedeemTemplate(
        redeem_type = 'reveal',
        title = 'Reveal | Twitch2BBR',
        prompt = 'Reveals the streamer for one Minute',
        cost = 500,
        is_global_cooldown_enabled = True,
        global_cooldown_seconds = 60
        )
        self.redeems_temps.append(reveal)
        
        
        zoomies = RedeemTemplate(
        redeem_type = 'zoomies',
        title = 'Zoomies | Twitch2BBR',
        prompt = '1 Minute of speed',
        cost = 500,
        is_global_cooldown_enabled = True,
        global_cooldown_seconds = 60
        )
        self.redeems_temps.append(zoomies)
        
        glass = RedeemTemplate(
        redeem_type = 'glass',
        title = 'Glass Mode | Twitch2BBR',
        prompt = '1 Minute of being like Glass',
        cost = 500,
        is_global_cooldown_enabled = True,
        global_cooldown_seconds = 60
        )
        self.redeems_temps.append(glass)
        
        freeze = RedeemTemplate(
        redeem_type = 'freeze',
        title = 'Freeze | Twitch2BBR',
        prompt = '10 sec Freezing',
        cost = 500,
        is_global_cooldown_enabled = True,
        global_cooldown_seconds = 60
        )
        self.redeems_temps.append(freeze)
        
        bleed = RedeemTemplate(
        redeem_type = 'bleed',
        title = 'Bleed | Twitch2BBR',
        prompt = '60s of bleeding very easily',
        cost = 500,
        is_global_cooldown_enabled = True,
        global_cooldown_seconds = 60
        )
        self.redeems_temps.append(bleed)
        
        turntables = RedeemTemplate(
        redeem_type = 'turntables',
        title = 'Turntables | Twitch2BBR',
        prompt = 'Switch the Team, how the turntables',
        cost = 500,
        is_global_cooldown_enabled = True,
        global_cooldown_seconds = 60
        )
        self.redeems_temps.append(turntables)
        
        melee = RedeemTemplate(
        redeem_type = 'melee',
        title = 'Melee | Twitch2BBR', # Needs Queue???
        prompt = 'Melee Only',
        cost = 500,
        is_global_cooldown_enabled = True,
        global_cooldown_seconds = 60
        )
        self.redeems_temps.append(melee)
    
    
    def build(self, broadcaster_id):
        redeems = []
        for redeem in self.redeems_temps:
            redeem.broadcaster_id = broadcaster_id
            redeems.append(redeem)
            
        return redeems
        
        
