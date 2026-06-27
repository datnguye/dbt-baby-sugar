from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static

from dbt_baby_sugar.ui.app.confirm_cancel import ConfirmCancelScreen


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        # A busy log-like background, so a bleed-through around the modal is
        # detectable in the rendered output.
        yield Static("\n".join(f"START sql view model thing_{i}" for i in range(40)))


async def _open_and_choose(button_id: str | None, key: str | None = None) -> bool | None:
    app = _Host()
    result: dict[str, bool | None] = {}
    async with app.run_test() as pilot:
        app.push_screen(ConfirmCancelScreen(), lambda r: result.__setitem__("r", r))
        await pilot.pause()
        if key is not None:
            await pilot.press(key)
        else:
            await pilot.click(f"#{button_id}")
        await pilot.pause()
    return result.get("r")


async def test_yes_dismisses_true() -> None:
    assert await _open_and_choose("yes") is True


async def test_no_dismisses_false() -> None:
    assert await _open_and_choose("no") is False


async def test_escape_keeps_running() -> None:
    assert await _open_and_choose(button_id=None, key="escape") is False


async def test_buttons_render_inside_the_dialog_border() -> None:
    # Guards the overflow bug where the buttons spilled below the dialog's bottom
    # border. Both button rows must sit strictly within the dialog's region.
    app = _Host()
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(ConfirmCancelScreen())
        await pilot.pause()
        await pilot.pause()
        dialog = app.screen.query_one("#dialog").region
        for button_id in ("yes", "no"):
            button = app.screen.query_one(f"#{button_id}").region
            assert button.y > dialog.y, f"#{button_id} starts above the top border"
            # Require real vertical slack below the buttons, not just non-overlap, so
            # a driver whose height math drifts a cell or two still can't clip them.
            assert button.bottom + 1 < dialog.bottom, f"#{button_id} too close to the bottom border"
            assert dialog.x < button.x and button.right < dialog.right


async def test_modal_paints_over_the_log_background() -> None:
    # Guards the bleed-through bug where the native dbt log showed around the
    # dialog. The row above the dialog must be the screen's opaque background, not
    # leftover log text bleeding through.
    app = _Host()
    async with app.run_test(size=(100, 24)) as pilot:
        app.push_screen(ConfirmCancelScreen())
        await pilot.pause()
        await pilot.pause()
        strip = next(iter(app.screen._compositor.render_strips()))
        assert strip.text.strip() == "", "log text bled through above the dialog"
        backgrounds = {seg.style.bgcolor for seg in strip if seg.style and seg.style.bgcolor}
        assert backgrounds, "the screen above the dialog was not painted opaque"
