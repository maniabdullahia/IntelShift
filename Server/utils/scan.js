function getNextScanAt(cadence, from = new Date()) {
  const nextScanAt = new Date(from);

  switch (cadence.toLowerCase()) {
    case "daily":
      nextScanAt.setDate(nextScanAt.getDate() + 1);
      break;

    case "2d":
      nextScanAt.setDate(nextScanAt.getDate() + 2);
      break;

    case "3d":
      nextScanAt.setDate(nextScanAt.getDate() + 3);
      break;

    case "5d":
      nextScanAt.setDate(nextScanAt.getDate() + 5);
      break;

    case "weekly":
      nextScanAt.setDate(nextScanAt.getDate() + 7);
      break;

    case "monthly":
      nextScanAt.setMonth(nextScanAt.getMonth() + 1);
      break;

    case "once":
      return null;

    default:
      throw new Error(`Unsupported cadence: ${cadence}`);
  }

  return nextScanAt;
}

export { getNextScanAt };