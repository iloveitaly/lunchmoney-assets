var cron = require('node-cron');

const schedule = process.env.SCHEDULE;

if (!schedule) {
  throw new Error('Missing SCHEDULE environment variable');
}

console.log("Starting with schedule:", schedule);

cron.schedule(schedule, () => {
  console.log(`Executing...`);
  require('child_process').spawn('bun', ['run', 'index.ts'], { stdio: 'inherit' });
});