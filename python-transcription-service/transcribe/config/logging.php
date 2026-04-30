<?php

use Monolog\Handler\NullHandler;
use Monolog\Handler\StreamHandler;
use Monolog\Handler\SyslogUdpHandler;

$is_debug = (bool)env('APP_DEBUG', false);

$slackChannel = function (?string $channel, string $emoji = '', bool $short = false, string $level = \Psr\Log\LogLevel::DEBUG): array {
    return [
        'driver'   => 'slack',
        'url'      => (string)env('LOG_SLACK_WEBHOOK_URL'),
        'channel'  => (string)$channel,
        'username' => 'Transcribe service',
        'emoji'    => $emoji,
        'short'    => $short,
        'level'    => $level,
    ];
};

$discordChannel = function (?string $webhook_url, string $avatar_url = '', string $level = \Psr\Log\LogLevel::DEBUG): array {
    return [
        'driver'       => 'monolog',
        'handler'      => \App\Services\Monolog\Handler\DiscordHandler::class,
        'handler_with' => [
            'webhook_url' => (string)$webhook_url,
            'username'    => 'Transcribe service',
            'avatar_url'  => $avatar_url,
            'level'       => $level,
        ],
    ];
};

return [

    /*
    |--------------------------------------------------------------------------
    | Default Log Channel
    |--------------------------------------------------------------------------
    |
    | This option defines the default log channel that gets used when writing
    | messages to the logs. The name specified in this option should match
    | one of the channels defined in the "channels" configuration array.
    |
    */

    'default' => env('LOG_CHANNEL', 'stack'),

    'suppress_duplication_interval' => $is_debug ? 01 : 15,

    /*
    |--------------------------------------------------------------------------
    | Log Channels
    |--------------------------------------------------------------------------
    |
    | Here you may configure the log channels for your application. Out of
    | the box, Laravel uses the Monolog PHP logging library. This gives
    | you a variety of powerful log handlers / formatters to utilize.
    |
    | Available Drivers: "single", "daily", "slack", "syslog",
    |                    "errorlog", "monolog",
    |                    "custom", "stack"
    |
    */

    'channels' => [
        'stack' => [
            'driver' => 'stack',
            'ignore_exceptions' => !$is_debug,
            'channels' => ['daily'],
        ],

        'single' => [
            'driver' => 'single',
            'path' => storage_path('logs/lumen.log'),
            'level' => 'debug',
        ],

        'daily' => [
            'driver' => 'daily',
            'path' => storage_path('logs/lumen.log'),
            'level' => 'debug',
            'days' => 7,
        ],

        //-------------------------------------------------------
        'exceptions-log'         => [
            'name'              => 'exceptions-log',
            // Период (в секундах), в течение которого повторяющиеся записи должны подавляться после отправки в лог
            'throttle_time'     => $is_debug ? 0 : 10,
            'driver'            => 'stack',
            'ignore_exceptions' => !$is_debug,
            'channels'          => array_filter([
                'daily',
                env('LOG_SLACK_CHANNEL_TRANSCRIBE_ERRORS') ? 'exceptions-log-slack' : null,
                env('LOG_DISCORD_WEBHOOK_URL_TRANSCRIBE_ERRORS') ? 'exceptions-log-discord' : null,
            ]),
            'tap'               => [
                // выполняются в обратном порядке
                \App\Services\Monolog\Logging\ServerLabelTap::class,
                \App\Services\Monolog\Logging\WebDataTap::class,
                \App\Services\Monolog\Logging\RequestDataTap::class,
            ]
        ],
        'exceptions-log-slack'   => $slackChannel(
            channel: env('LOG_SLACK_CHANNEL_TRANSCRIBE_ERRORS', '#transcribe_errors'),
            emoji: ':boom:'
        ),
        'exceptions-log-discord' => $discordChannel(
            webhook_url: env('LOG_DISCORD_WEBHOOK_URL_TRANSCRIBE_ERRORS'),
            avatar_url: 'https://a.slack-edge.com/production-standard-emoji-assets/14.0/google-large/1f4a5@2x.png'
        ),

        'transcribe-errors-log'         => [
            'name'              => 'transcribe-errors-log',
            'driver'            => 'stack',
            'ignore_exceptions' => !$is_debug,
            'channels'          => array_filter([
                'daily',
                env('LOG_SLACK_CHANNEL_TRANSCRIBE_ERRORS') ? 'transcribe-errors-log-slack' : null,
                env('LOG_DISCORD_WEBHOOK_URL_TRANSCRIBE_ERRORS') ? 'transcribe-errors-log-discord' : null,
            ]),
            'tap'               => [
                \App\Services\Monolog\Logging\SuppressDuplicationTap::class,
                // выполняются в обратном порядке
                \App\Services\Monolog\Logging\ServerLabelTap::class,
            ]
        ],
        'transcribe-errors-log-slack'   => $slackChannel(
            channel: env('LOG_SLACK_CHANNEL_TRANSCRIBE_ERRORS', '#transcribe_errors'),
            short: true
        ),
        'transcribe-errors-log-discord' => $discordChannel(
            webhook_url: env('LOG_DISCORD_WEBHOOK_URL_TRANSCRIBE_ERRORS'),
        ),

        'papertrail' => [
            'driver' => 'monolog',
            'level' => 'debug',
            'handler' => SyslogUdpHandler::class,
            'handler_with' => [
                'host' => env('PAPERTRAIL_URL'),
                'port' => env('PAPERTRAIL_PORT'),
            ],
        ],

        'stderr' => [
            'driver' => 'monolog',
            'handler' => StreamHandler::class,
            'with' => [
                'stream' => 'php://stderr',
            ],
        ],

        'syslog' => [
            'driver' => 'syslog',
            'level' => 'debug',
        ],

        'errorlog' => [
            'driver' => 'errorlog',
            'level' => 'debug',
        ],

        'null' => [
            'driver' => 'monolog',
            'handler' => NullHandler::class,
        ],
    ],

];
