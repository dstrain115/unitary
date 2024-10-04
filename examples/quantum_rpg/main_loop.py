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

import enum
import textwrap
from typing import Optional, Sequence

from . import ascii_art
from . import battle
from . import classes
from . import exceptions
from . import game_state
from . import input_helpers
from . import npcs
from . import world
from . import xp_utils
from .final_state_preparation import final_state_world


class Error(Exception):
    """Base class for locally defined exceptions."""
    pass


class AmbiguousCommandError(Error):
    """Raised when entered command is ambiguous."""
    pass


class Command(enum.Enum):
    """Enumeration of available commands."""

    LOAD = "load"
    LOOK = "look"
    STATUS = "status"
    SAVE = "save"
    HELP = "help"
    QUANTOPEDIA = "quantopedia"
    QUIT = "Quit"

    @classmethod
    def parse(cls, s: str) -> Optional["Command"]:
        """Parses a string as a command.

        Allows prefixes, like 'e' to be parsed as EAST.
        """
        if not s:
            return None
        # Quit is a special case, it's case-sensitive. It's matched first before
        # input is lower-cased and matched against every other command.
        if cls.QUIT.value.startswith(s):
            return cls.QUIT
        lower_s = s.lower()
        candidates = []
        for cmd in cls:
            # Quit has already been handled above.
            if cmd == cls.QUIT:
                continue
            if cmd.value.startswith(lower_s):
                candidates.append(cmd)
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise AmbiguousCommandError
        return None

    @classmethod
    def help(cls) -> str:
        cmds = ["Available commands:"]
        for cmd in Command:
            cmds.append(f"  {cmd.value}")
        return "\n".join(cmds)


class MainLoop:
    def __init__(self, world: world.World, state: game_state.GameState):
        self.world = world
        self.game_state = state

    @property
    def party(self):
        return self.game_state.party

    @property
    def file(self):
        return self.game_state.file

    def print_status(self):
        print(
            "\n".join(
                f"{idx+1}) {qar.qar_status()}"
                for idx, qar in enumerate(self.game_state.party)
            ),
            file=self.file,
        )

    def loop(self, user_input: Optional[Sequence[str]] = None) -> None:
        """Main loop of Quantum RPG.

        Loop by getting user input and then acting on it.
        """
        print_room_description = True
        try:
            while True:
                if print_room_description:
                    print(self.world.current_location, file=self.file)
                    if self.world.current_location.encounters:
                        result = None
                        # If this location has random encounters, then see if any will
                        # trigger.  If so, initiate the battle.
                        for random_encounter in self.world.current_location.encounters:
                            if random_encounter.will_trigger():
                                if random_encounter.description:
                                    print(random_encounter.description, file=self.file)
                                current_battle = random_encounter.initiate(
                                    self.game_state
                                )
                                result = current_battle.loop()
                                self.world.current_location.remove_encounter(
                                    random_encounter
                                )

                                if result == battle.BattleResult.PLAYERS_WON:
                                    awarded_xp = current_battle.xp
                                    xp_utils.award_xp(self.game_state, awarded_xp)
                                elif result == battle.BattleResult.PLAYERS_DOWN:
                                    raise exceptions.UntimelyDeathException(
                                        "You have been defeated!"
                                    )
                                break
                        if result is not None:
                            # Reprint location description now that encounter is over.
                            print(self.world.current_location, file=self.file)

                print_room_description = True
                current_input = self.game_state.get_user_input(">")
                self.game_state.current_input = current_input
                cmd = world.Direction.parse(current_input)
                if cmd is not None:
                    new_location = self.world.move(cmd)
                    if new_location is not None:
                        self.game_state.current_location_label = new_location.label
                    continue
                action = self.world.current_location.get_action(current_input)
                if action is not None:
                    if isinstance(action, str):
                        print(action, file=self.file)
                    elif callable(action):
                        msg = action(self.game_state, self.world)
                        if msg:
                            print(msg, file=self.file)
                    print_room_description = False
                    continue
                try:
                    input_cmd = Command.parse(current_input)
                except AmbiguousCommandError:
                    print(f"Ambiguous command '{current_input}'.",
                          Command.help(),
                          file=self.file)
                    print_room_description = False
                    continue
                if input_cmd == Command.QUIT:
                    return
                elif input_cmd == Command.STATUS:
                    self.print_status()
                    print_room_description = False
                elif input_cmd == Command.HELP:
                    print(ascii_art.HELP, file=self.file)
                    print_room_description = False
                elif input_cmd == Command.QUANTOPEDIA:
                    print(file=self.file)
                    for npc_class in npcs.Npc.__subclasses__():
                        print(npc_class.__name__, file=self.file)
                        print(
                            textwrap.indent(npc_class.quantopedia_entry(), "  "),
                            file=self.file)
                        print(file=self.file)
                    print_room_description = False
                elif input_cmd == Command.LOAD:
                    print(
                        "Paste the save file here to load the game from that point.",
                        file=self.file,
                    )
                    save_file = self.game_state.get_user_input("")
                    if self.game_state.with_save_file(save_file) is None:
                        print("Unrecognized save file.", file=self.file)
                    else:
                        self.world.current_location = self.world.locations[
                            self.game_state.current_location_label
                        ]
                elif input_cmd == Command.SAVE:
                    print(
                        "Use this code to return to this point in the game:",
                        file=self.file,
                    )
                    print(self.game_state.to_save_file(), file=self.file)
                    print("")
                    print_room_description = False
                elif input_cmd == Command.LOOK:
                    print(self.world.current_location, file=self.file)
                    print_room_description = False
                else:
                    print(
                        f"I did not understand the command {current_input}.",
                        file=self.file,
                    )
                    print_room_description = False
        except exceptions.UntimelyDeathException as e:
            print(e, file=self.file)
            print(ascii_art.RIP_TOP, file=self.file)
            for qar in self.game_state.party:
                print(f"     |       | {qar.name: ^16} |", file=self.file)
            print(ascii_art.RIP_BOTTOM, file=self.file)
            print(
                "You have been measured and were found wanting.",
                file=self.file,
            )
            print("Better luck next repetition.", file=self.file)
            return


def main(state: game_state.GameState) -> None:
    """Initial start screen for Quantum RPG.

    Display intro image and then get initial choice(s)
    to start the game.
    """
    main_loop = None
    print(ascii_art.TITLE_SCREEN, file=state.file)
    while not main_loop:
        print(ascii_art.START_MENU, file=state.file)
        menu_choice = int(
            input_helpers.get_user_input_number(
                state.get_user_input, ">", 4, file=state.file
            )
        )
        if menu_choice == 1:
            print(ascii_art.INTRO_STORY, file=state.file)
            name = input_helpers.get_user_input_qaracter_name(
                state.get_user_input, "your initial Analyst qaracter", file=state.file
            )
            qar = classes.Analyst(name)
            state.party.append(qar)
            main_loop = MainLoop(world.World(final_state_world.WORLD), state)
        elif menu_choice == 2:
            print(
                "Paste the save file here to load the game from that point.",
                file=state.file,
            )
            save_file = state.get_user_input("")
            new_state = state.with_save_file(save_file)
            if new_state is None:
                print("Unrecognized save file.", file=state.file)
                continue
            main_loop = MainLoop(world.World(final_state_world.WORLD), new_state)
            main_loop.world.current_location = main_loop.world.locations[
                state.current_location_label
            ]
        elif menu_choice == 3:
            print(ascii_art.HELP, file=state.file)
        elif menu_choice == 4:
            return
    main_loop.loop()


if __name__ == "__main__":
    main(game_state.GameState(party=[]))
