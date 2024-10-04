# Copyright 2023 The Unitary Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Dict, List, Optional, Sequence, TextIO

import sys

from . import input_helpers
from . import qaracter


_SAVE_DELIMITER = ";"
_DICT_DELIMITER = ":"
_QUANTOPEDIA_KEY = "qp"


class GameState:
    def __init__(
        self,
        party: List[qaracter.Qaracter],
        current_location_label: str = "",
        state_dict: Optional[Dict[str, str]] = None,
        user_input: Optional[Sequence[str]] = None,
        file: TextIO = sys.stdout,
    ):
        self.party = party
        self.current_location_label = current_location_label
        self.current_input = ""
        self.state_dict = state_dict or {}
        self.user_input = user_input
        self.get_user_input = input_helpers.get_user_input_function(user_input)
        self.file = file

    def set_quantopedia(self, num: int) -> None:
        """Convenience method for setting a quantopedia bit.

        The quantopedia is repesented by a bitstring in the
        state_dict.  During a battle, if the bit for the enemy
        NPC is set, then the entry for that type of NPC is displayed.
        """
        if _QUANTOPEDIA_KEY not in self.state_dict:
            self.state_dict[_QUANTOPEDIA_KEY] = "0"
        quantopedia_num = int(self.state_dict[_QUANTOPEDIA_KEY]) | num
        self.state_dict[_QUANTOPEDIA_KEY] = str(quantopedia_num)

    def has_quantopedia(self, num: int) -> bool:
        """Convenience method for getting  a quantopedia bit.

        The quantopedia is repesented by a bitstring in the
        state_dict.  During a battle, if the bit for the enemy
        NPC is set, then the entry for that type of NPC is displayed.
        """
        if _QUANTOPEDIA_KEY not in self.state_dict:
            return False
        quantopedia_num = int(self.state_dict[_QUANTOPEDIA_KEY])
        return quantopedia_num & num != 0

    def with_save_file(self, save_file) -> "Optional[GameState]":
        """Modifies GameState object in place to load info from save file.

        Overwrites the party, state dictionary, and current location.

        Note that this should be done if loading information during a game
        in progress, since we don't want to lose the state of where we
        are in parsing the user input.
        """
        lines = save_file.split(_SAVE_DELIMITER)
        if len(lines) < 2:
            return None
        self.current_location_label = lines[0]
        party: List[qaracter.Qaracter] = []
        try:
            num_party = int(lines[1])
        except ValueError:
            return None
        if len(lines) < 2 + num_party:
            return None
        for party_idx in range(2, 2 + num_party):
            party.append(qaracter.Qaracter.from_save_file(lines[party_idx]))
        state_dict = {}
        for line in lines[2 + num_party :]:
            dict_value = line.split(":")
            if len(dict_value) < 2:
                continue
            state_dict[dict_value[0]] = dict_value[1]
        self.state_dict = state_dict
        self.party = party
        return self

    @classmethod
    def from_save_file(
        cls,
        save_file: str,
        user_input: Optional[Sequence[str]] = None,
        file: TextIO = sys.stdout,
    ) -> "GameState":
        """Creates a new Gamestate from a save file."""
        return cls([], "", {}, user_input, file).with_save_file(save_file)

    def to_save_file(self) -> str:
        """Serializes a GameState into a string for saving/loading."""
        s = f"{self.current_location_label}{_SAVE_DELIMITER}{len(self.party)}{_SAVE_DELIMITER}"
        for p in self.party:
            s += p.to_save_file() + _SAVE_DELIMITER
        for k, v in self.state_dict.items():
            s += f"{k}{_DICT_DELIMITER}{v}{_SAVE_DELIMITER}"
        return s[:-1]
