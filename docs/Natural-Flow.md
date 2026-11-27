# Natural flow

The application uses **Tactile flow**, selected by the owner from three interactive
motion studies on 12 October 2026. The motion belongs to the action: a surface makes
room, a card turns, a day moves, and information settles where it can be read.

## Shared rules

`static/motion.js` owns the spring: stiffness 180, damping 20, mass 1. These are the
parameters of the chosen study. Spatial channels retain position and velocity when
their destination changes. Completed channels start their next action from current
DOM geometry, including responsive sizes and instant display changes.

The same solver supplies the CSS spring curve and settling time. Colour, focus and
small status feedback use 100 ms ease-out. User-intent delays, such as the 500 ms
hold that turns a card, remain separate from animation timing.

Movement stays restrained: ordinary entry travels 20 px, updated information 8 px,
and the four natal pillars enter 22 ms apart. Relationship ink follows structural
settling. There are no decorative repeating animations.

## Interaction contract

| Interaction | Motion and identity |
|---|---|
| Landing, chart, Today, Settings and comparison | The incoming surface settles into place. Fixed panels and hints retain their viewport coordinates. |
| A new birth | The pillars enter together in reading order with a short stagger. |
| Language, convention and returning to the same birth | Existing identity is preserved; the natal entrance does not replay. |
| Card faces | Rotation and height share one live spring. Reversing changes its destination, preserving its position and velocity. |
| Hidden stems and reading disclosures | Height and opacity settle together. An open disclosure returns to intrinsic height so responsive content can grow. |
| Detail panels | The chart makes room through a coordinated layout spring. The panel settles in or out; close immediately updates logical state and returns focus. Retiring content is cleared after its visual exit. |
| Topic and reading changes | The affected information settles in place. Today topics select the current answer and do not ask for another day computation. |
| Day navigation | Retained day nodes move and scale with the shared spring. Dragging is direct manipulation; release starts from the displayed position. |
| Native dialogs | Native open, close, focus and request-cancellation semantics remain intact. Discrete display and overlay transitions carry the visual entrance and exit. |
| Saved charts, My chart, couples and Settings | Changed information uses the same local content motion and immediate status feedback. |
| Luck and life views | The natal columns make room for the fifth pillar; the chosen phase and folded life view use the same information and layout rules. |
| Comparison swap | Frame positions follow their chart identities through a shared layout transition; embedded charts do not add independent natal entrances. |
| Explorer | Pan, zoom-to-fit and parameter-pane layout use the shared model. Repeating decorative rings are removed. |
| Notices and toasts | Feedback enters and leaves coherently. Toast text remains present throughout its exit. An error said about a page leaves, in its exit, when another page is followed to; a confirmation stays its time. |

## Accessibility and lifecycle

Reduced motion removes spatial, resize, colour and decorative animation across both
application surfaces. Switching the preference on finishes active channels at their
destinations. Printing also settles active motion before rendering static content.
Direct viewport resizing settles active channels so offsets and fixed sizes from
the previous responsive layout cannot constrain the new one.

Animations neither defer account operations nor change chart computation. A surface
that is closed accepts no interaction. Retired account content is cleared when its
containing view leaves, and detached actors stop participating in the frame loop.
Actors in a departed view settle their logical state and release temporary sizes;
scrolling stops without resetting the hidden view's saved position.

Browser regressions wait for both native animations and the shared motion runtime.
`tests/browser/motion.test.mjs` covers reversals, responsive disclosures, panel
continuity, reduced motion and updates to the same birth in Chromium and WebKit.
