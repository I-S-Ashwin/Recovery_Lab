// vinext's successful forced exit races closing native handles after static export
// on Windows. Let the event loop drain on success; preserve every failure exit.
if (process.platform === 'win32') {
  const forcedExit = process.exit.bind(process);
  process.exit = (code = 0) => {
    if (code === 0 || code === '0') {
      process.exitCode = 0;
      return;
    }
    return forcedExit(code);
  };
}
