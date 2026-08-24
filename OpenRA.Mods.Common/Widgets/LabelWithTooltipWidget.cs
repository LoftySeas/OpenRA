#region Copyright & License Information
/*
 * Copyright (c) The OpenRA Developers and Contributors
 * This file is part of OpenRA, which is free software. It is made
 * available to you under the terms of the GNU General Public License
 * as published by the Free Software Foundation, either version 3 of
 * the License, or (at your option) any later version. For more
 * information, see COPYING.
 */
#endregion

using System;
using OpenRA.Widgets;

namespace OpenRA.Mods.Common.Widgets
{
	public class LabelWithTooltipWidget : LabelWidget
	{
		public readonly string TooltipTemplate;
		public readonly string TooltipContainer;
		protected Lazy<TooltipContainerWidget> tooltipContainer;

		public Func<string> GetTooltipText = () => "";

		// When true and the text overflows the widget bounds, the title scrolls horizontally
		// while the mouse is hovering over the widget, then loops. Used in the mission browser
		// for bilingual mission names that don't fit at the available width. The static
		// tooltip behavior (showing the full text) is still available as a fallback for
		// non-scrolling consumers - it is only suppressed when GetTooltipText returns the
		// truncated text, which is no longer the case once ScrollOnHover is enabled and the
		// caller uses the full untruncated text via GetText.
		public bool ScrollOnHover;

		// Pixels advanced per Tick. ~1 px per tick at 25 Hz tick rate is a comfortable
		// reading speed. Tuned by feel; small enough to be readable, fast enough to finish
		// a 300 px overflow in ~12 seconds.
		public int ScrollSpeed = 1;

		// Ticks to wait at the wrap-around point so the reader has time to register the start
		// of the loop before the text jumps back to the beginning.
		public int ScrollResetPauseTicks = 30;

		bool isHovered;
		int scrollOffset;
		int scrollPauseTicks;
		int endDwellTicks;

		[ObjectCreator.UseCtor]
		public LabelWithTooltipWidget(ModData modData)
			: base(modData)
		{
			tooltipContainer = Exts.Lazy(() =>
				Ui.Root.Get<TooltipContainerWidget>(TooltipContainer));
		}

		protected LabelWithTooltipWidget(LabelWithTooltipWidget other)
			: base(other)
		{
			TooltipTemplate = other.TooltipTemplate;
			TooltipContainer = other.TooltipContainer;

			tooltipContainer = Exts.Lazy(() =>
				Ui.Root.Get<TooltipContainerWidget>(TooltipContainer));

			GetTooltipText = other.GetTooltipText;
			ScrollOnHover = other.ScrollOnHover;
			ScrollSpeed = other.ScrollSpeed;
			ScrollResetPauseTicks = other.ScrollResetPauseTicks;
		}

		public override LabelWithTooltipWidget Clone() { return new LabelWithTooltipWidget(this); }

		public override void MouseEntered()
		{
			if (ScrollOnHover)
			{
				isHovered = true;

				// Start with a brief pause so the user can register the start of the text
				// before it begins moving.
				scrollPauseTicks = ScrollResetPauseTicks / 2;
			}

			if (TooltipContainer == null)
				return;

			if (GetTooltipText != null)
				tooltipContainer.Value.SetTooltip(TooltipTemplate, new WidgetArgs() { { "getText", GetTooltipText } });
		}

		public override void MouseExited()
		{
			if (ScrollOnHover)
			{
				isHovered = false;
				scrollOffset = 0;
				scrollPauseTicks = 0;
				endDwellTicks = 0;
				ScrollOffsetX = 0;
			}

			// Only try to remove the tooltip if we know it has been created
			// This avoids a crash if the widget (and the container it refers to) are being removed
			if (TooltipContainer != null && tooltipContainer.IsValueCreated)
				tooltipContainer.Value.RemoveTooltip();
		}

		public override void Tick()
		{
			if (!ScrollOnHover || !isHovered)
				return;

			var text = GetText();
			if (string.IsNullOrEmpty(text))
				return;

			if (!Game.Renderer.Fonts.TryGetValue(Font, out var font))
				return;

			// Only scroll when the text actually overflows. Without overflow, ScrollOffsetX
			// stays at 0 and the label renders normally.
			var textWidth = font.Measure(text).X;
			if (textWidth <= Bounds.Width)
			{
				ScrollOffsetX = 0;
				return;
			}

			// End-of-scroll dwell: pause at the far end with the last word fully visible before
			// snapping back to the beginning. Without this, the text would keep marching left
			// into blank space until scrollOffset reached textWidth, leaving a long empty tail.
			if (endDwellTicks > 0)
			{
				endDwellTicks--;
				if (endDwellTicks == 0)
				{
					// Snap back to the start and arm the start-of-cycle pause.
					scrollOffset = 0;
					scrollPauseTicks = ScrollResetPauseTicks;
				}

				ScrollOffsetX = scrollOffset;
				return;
			}

			if (scrollPauseTicks > 0)
			{
				scrollPauseTicks--;
				return;
			}

			scrollOffset += ScrollSpeed;
			var maxOffset = textWidth - Bounds.Width;
			if (scrollOffset >= maxOffset)
			{
				// Clamp at the end (last character flush with the right edge) and dwell briefly.
				scrollOffset = maxOffset;
				endDwellTicks = ScrollResetPauseTicks;
			}

			ScrollOffsetX = scrollOffset;
		}
	}
}
