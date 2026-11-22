# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The setup overlay: installing content with a showcase drawn over the viewport.

PROTOTYPE. The download is faked (`state.FakeWorker`); everything else is the
shape of the real thing: `state` holds the download the overlay and the sidebar
panel both read, `draw` paints anti-aliased cards, images and text with the gpu
module, `screens` are the pack list, the slides and the done screen, and
`operator` is the modal operator that shows them and can be dismissed while the
download goes on.
"""
