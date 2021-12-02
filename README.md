## Welcome to Bjarne's Squash - Remote mode!
This is a new and improved version of the forked squash source code, where the following features has been added:
- Realistic ball bounce angles
- Ball bounce decay
- Ball velocity decay
- A occasional visit from the former president of United States, Donald J. Trump
- Filtered paddle movement
- Penalties for blocking the other players shot
- Fixed the budging bug (Really don't know why it works now)
- Added team name feature
- Added end game when a player hits 10 points for whith a two-point lead
- Added reduced paddle size after x amount of time to increase difficulty
- Added ball velocity increase after x amount of time for the same reason as above
- Added increased chance of a visit from Donald Trump after x amount of time
- And most important of all, added REST API for paddle control and screen request for AI controlled Squash.


## Squash

A simple game based on Squash written in Python 2.7 with Pygame 1.9.

Gameplay:

- There are two players in the game and they are restricted to moving in the bottom half of the court, but each player can freely cross over into the other's side of the court.
- The Green Player (left player) uses the left controls, and Blue Player (right player) uses the right controls.
- The coloured circle at the top of the screen indicates which color player should go for the ball.
- The goal of the game is to hit the ball so it bounces to the top of the screen. Then your opponent must hit the ball. The player who keeps the ball in the court and does not hit the ball out of turn wins.
- If you don't hit the ball and it goes to the bottom of the screen, your opponent wins a point.
- If you hit the ball out of turn or the ball hits you, your opponent wins a point.
- If you miss the ball or hit it out of turn you become the server and the other player must go for the ball.
- Players can be crafty and budge the other player out of the way by banging into them so they miss the ball.

Controls:

Left (Green) player:

- W (up)
- A (left)
- S (down)
- D (right)

Right (Blue) player:

- Up Arrow (up)
- Left Arrow (left)
- Down Arrow (down)
- Right Arrow (right)

Press M to mute the game.

Press Q to quit the game.
