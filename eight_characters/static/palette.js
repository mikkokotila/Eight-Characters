// The chart's commands, found by typing (⌘K or Ctrl+K). A command runs as its control
// would; the chart says what there is to run.
(() => {
  const create = ({ dialog, escape: esc }) => {
    const input = dialog.querySelector('#palette-input');
    const list = dialog.querySelector('#palette-list');
    const empty = dialog.querySelector('#palette-empty');
    if (!input || !list || !empty) throw new Error('Command palette is incomplete.');
    let commands = [];
    let found = [];
    let active = 0;

    const matches = (command, words) => {
      const text = `${command.label} ${command.group}`.toLocaleLowerCase();
      return words.every((word) => text.includes(word));
    };
    const draw = () => {
      const words = input.value.toLocaleLowerCase().split(/\s+/).filter(Boolean);
      found = commands.filter((command) => matches(command, words));
      active = Math.min(active, Math.max(found.length - 1, 0));
      list.innerHTML = found.map((command, index) => `
        <li role="option" id="palette-option-${index}" class="palette-option" data-index="${index}"
          aria-selected="${index === active}">
          <span class="palette-label">${esc(command.label)}</span>
          <span class="palette-group">${esc(command.group)}</span>
        </li>`).join('');
      empty.classList.toggle('hidden', found.length > 0);
      if (found.length === 0) {
        input.removeAttribute('aria-activedescendant');
        return;
      }
      input.setAttribute('aria-activedescendant', `palette-option-${active}`);
      list.children[active].scrollIntoView({ block: 'nearest' });
    };
    // The palette closes first, and the browser gives focus back to where it was, so
    // that the command moves it on if it moves focus at all.
    const run = (index) => {
      const command = found[index];
      if (!command) return;
      dialog.close();
      command.run();
    };

    input.addEventListener('input', () => {
      active = 0;
      draw();
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (found.length === 0) return;
        active = (active + (event.key === 'ArrowDown' ? 1 : -1) + found.length) % found.length;
        draw();
      } else if (event.key === 'Enter') {
        event.preventDefault();
        run(active);
      }
    });
    // A pointer leaves the typing where it is, and a click runs the command.
    list.addEventListener('mousedown', (event) => event.preventDefault());
    list.addEventListener('click', (event) => {
      const option = event.target.closest('[data-index]');
      if (option) run(Number(option.dataset.index));
    });
    const open = (available) => {
      commands = available;
      input.value = '';
      active = 0;
      draw();
      dialog.showModal();
      input.focus();
    };
    return { open };
  };
  window.EC_PALETTE = { create };
})();
