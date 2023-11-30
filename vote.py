

import asyncio
import datetime
import json
import math

import requests
from broadcaster import Broadcaster
from logger import Logger


class Vote:
    broadcaster: Broadcaster
    voted: list
    endpoint:str
    
    def __init__(self, broadcaster: Broadcaster, l:Logger, endpoint:str) -> None:
        self.broadcaster = broadcaster
        self.l = l
        self.isRunning = False
        self.choice = []
        self.voted = []
        self.vote_on_going = False
        self.endpoint = endpoint
        
        
        
        pass
    
    def reset_choices(self):
        self.l.info(f'Resetting Vote for {self.broadcaster.twitch_login}')
        self.choice[0] = 0
        self.choice[1] = 0
        self.choice[2] = 0
        self.choice[3] = 0
        self.voted = []
    
    async def vote(self):
        self.l.info(f'Voting enabled for {self.broadcaster.twitch_login} {self.isRunning}')
        while(self.isRunning):
            await asyncio.sleep(2)
            self.l.info(f'Vote for {self.broadcaster.twitch_login} Started, waiting on spawn')
            vote_start = datetime.datetime.now()
            while(self.vote_on_going):
                await asyncio.sleep(2)
                self.l.info(f'Vote for {self.broadcaster.twitch_login} Updating')   
                await self.update_vote(math.floor((vote_start+datetime.timedelta(seconds=30)-datetime.datetime.now()).total_seconds()))
                if(datetime.datetime.now() - vote_start >= datetime.timedelta(seconds=30)):  # time to vote
                    self.end_vote()
                    
                    await asyncio.sleep(120) # time till next vote
        self.l.info(f'Voting stopped for {self.broadcaster.twitch_login} {self.isRunning}')
        
        
    async def update_vote(self, time:int):
        self.l.info(f'Updated vote for {self.broadcaster.twitch_login}')
        
        data = {
            "EventType": "VoteOnGoing",
            "SteamId": self.broadcaster.steam_id,
            "Choices": self.choice,
            "Time": time
        }
        await self.POST(data)
    
    async def end_vote(self):
        self.l.info(f'Ended vote for {self.broadcaster.twitch_login}')
        
        data = {
            "EventType": "VoteEnd",
            "SteamId": self.broadcaster.steam_id,
            "Choices": self.choice
        }
        await self.POST(data)
        self.reset_choices()
        
        
    async def POST(self, data):
        # Convert the data to JSON format
        json_data = json.dumps(data)

        self.l.info(f'Data ready to send: {json_data}')
        

        # Make the POST request
        response = requests.post(self.endpoint, json=json_data)

        # Check if the request was successful (status code 2xx)
        if response.ok:
            return f'Sucessfully updated Vote for {self.broadcaster.twitch_login}({self.broadcaster.steam_id})'
        else:
            # If the request was unsuccessful, raise an exception with the error message
            response.raise_for_status()
            return f'Error updating Vote for {self.broadcaster.twitch_login}({self.broadcaster.steam_id})'
        
    
    async def register_vote(self, choice:int):
        self.choice[choice] += 1