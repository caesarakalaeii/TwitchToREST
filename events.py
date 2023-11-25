
class Event:
    '''
    Class representing a twitchbased Event to easily convert the needed data into json
    '''
    event_type: str
    steam_id:str
    username: str
    broadcaster: str
    message: str = None
    
    def __init__(self, broadcaster:str, username:str, steam_id:str, message:str = None):
        self.broadcaster = broadcaster
        self.username = username
        self.message = message
    
    def to_json_dict(self):
        '''
        Returns a dict to use in quarts jsonify filled with the event's data and type
        '''
        base = {
            'EventType': self.event_type,
            'Username': self.username,
            'Broadcaster': self.broadcaster,
        }
        if not self.message == None:
            base.update({'Message': self.message})
        
        return base
    
class Follow(Event):
    '''
    Class representing a twitchbased follow Event to easily convert the needed data into json
    '''
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, message: str = None):
        self.event_type = 'follow'
        super().__init__(broadcaster, username,steam_id, message)
    
    def to_json_dict(self):
        return super().to_json_dict()
    

class Sub(Event):
    '''
    Class representing a twitchbased subscribtion Event to easily convert the needed data into json
    '''
    event_type = 'sub'
    tier: int
    total_time: int
    streak: int
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, tier:int, total_time:int, streak:int, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'sub'
        self.tier: int = tier
        self.total_time: int = total_time
        self.streak: int = streak
    
    def to_json_dict(self):
        base = super().to_json_dict()
        base.update({
            'Tier': self.tier,
            'TotalTime': self.total_time,
            'Streak': self.streak
        })
        return base
    
    
    
class SubBomb(Event):
    '''
    Class representing a twitchbased multi subscribtion (subbomb) Event to easily convert the needed data into json
    '''
    event_type:str
    amount: int
    tier: int
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, tier: int, amount, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'subbomb'
        self.amount = amount
        self.tier = tier
    
    def to_json_dict(self):
        base = super().to_json_dict()
        base.update({
            'Tier': self.tier,
            'Amount': self.amount
        })
        return base

class Gift(Event):
    '''
    Class representing a twitchbased gift event to easily convert the needed data into json
    '''
    
    event_type = 'gift'
    gifter_name: str
    tier: int
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, gifter_name:str, tier:int, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'gift'
        self.gifter_name = gifter_name
        self.tier = tier
    
    def to_json_dict(self):
        return {
            'Tier': self.tier,
            'GifterName': self.gifter_name
        }
    
class Redeem(Event):
    '''
    Class representing a twitchbased redeem event to easily convert the needed data into json
    '''
    
    event_type: str
    redeem_id: str
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, redeem_id: str, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'redeem'
        self.redeem_id = redeem_id
    
    def to_json_dict(self):
        return {
            'RedeemId': self.redeem_id
        }
    
class Bits(Event):
    '''
    Class representing a twitchbased bit event to easily convert the needed data into json
    '''
    
    
    event_type: str
    amount: int
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, amount:int, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'bits'
        self.amount = amount
    
    
    def to_json_dict(self):
        return {
            'Amount': self.amount

        }
    
class Raid(Event):
    '''
    Class representing a twitchbased raid event to easily convert the needed data into json
    '''
    
    event_type:str
    amount: int
    
    def __init__(self, broadcaster: str, username: str, steam_id:str, amount:int, message: str = None):
        super().__init__(broadcaster, username, steam_id, message)
        self.event_type = 'raid'
        self.amount = amount
    
    def to_json_dict(self):
        return {
            'Amount': self.amount

        }