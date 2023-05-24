from typing import List, Optional, Sequence
import enum
import io
import sys

import unitary.examples.quantum_rpg.ascii_art as ascii_art
import unitary.examples.quantum_rpg.battle as battle
import unitary.examples.quantum_rpg.encounter as encounter
import unitary.examples.quantum_rpg.qaracter as qaracter
import unitary.examples.quantum_rpg.world as world


class Command(enum.Enum):
    """Command parsing utility.

    Currently only supports 'quit' but future expansion planned.
    """

    QUIT = "quit"

    @classmethod
    def parse(cls, s: str) -> Optional["Command"]:
        """Parses a string as a Direction.

        Allows prefixes, like 'e' to be parsed as EAST.
        """
        lower_s = s.lower()
        for cmd in Command:
            if cmd.value.startswith(lower_s):
                return cmd


class MainLoop:
    def __init__(
        self,
        party: List[qaracter.Qaracter],
        world: world.World,
        file: io.IOBase = sys.stdout,
    ):
        self.world = world
        self.file = file
        self.party = party


    def print_title_screen(self):
        print(ascii_art.TITLE_SCREEN, file=self.file)

    def loop(self, user_input: Optional[Sequence[str]] = None) -> None:
        """Full battle loop until one side is defeated.

        Returns the result of a battle as an enum.
        """
        if user_input is not None:
            user_input = iter(user_input)
            get_user_input = lambda _: next(user_input)
        else:
            get_user_input = input
        while True:
            print(self.world.current_location, file=self.file)
            if self.world.current_location.encounters:
                result = None
                for random_encounter in self.world.current_location.encounters:
                    if random_encounter.will_trigger():
                        if random_encounter.description:
                            print(random_encounter.description, file=self.file)
                        battle = random_encounter.initiate(self.party, file=self.file)
                        result = battle.loop(get_user_input=get_user_input)
                        self.world.current_location.remove_encounter(random_encounter)

                        # TODO(dstrain): Resolve battle and award XP.
                        break
                if result is not None:
                    # Reprint location description now that encounter is over.
                    print(self.world.current_location, file=self.file)

            current_input = get_user_input(">")
            cmd = world.Direction.parse(current_input)
            if cmd is not None:
                self.world.move(cmd)
                continue
            cmd = Command.parse(current_input)
            if cmd == Command.QUIT:
                return
            else:
                print(
                    f"I did not understand the command {current_input}", file=self.file
                )
