<?php

namespace App\Console;

use App\Console\Commands\Cron\QueueStatGrafana;
use App\Console\Commands\MyTest;
use App\Console\Commands\MyTest__;
use App\Console\Commands\SendMessageToLogCommand;
use Illuminate\Console\Scheduling\Event;
use Illuminate\Console\Scheduling\Schedule;
use Laravel\Lumen\Console\Kernel as ConsoleKernel;

class Kernel extends ConsoleKernel
{
    /**
     * The Artisan commands provided by your application.
     *
     * @var array
     */
    protected $commands = [
        QueueStatGrafana::class,
        SendMessageToLogCommand::class,
        MyTest::class,
    ];

    /**
     * Define the application's command schedule.
     *
     * @param Schedule $schedule
     * @return void
     */
    protected function schedule(Schedule $schedule)
    {
        self::scheduleCommand($schedule, QueueStatGrafana::class)->everyMinute();
    }

    /**
     * Define the application's command schedule with default parameters
     *
     * @param Schedule $schedule
     * @param string $class
     * @param array $parameters
     * @return Event
     */
    private static function scheduleCommand(Schedule $schedule, string $class, array $parameters = [])
    {
        return $schedule->command($class, $parameters)
            ->runInBackground()
            ->onOneServer();
    }

}
