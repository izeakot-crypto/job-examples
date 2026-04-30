<?php
/**
 * https://discord.com/developers/docs/resources/webhook
 */

namespace App\Services\Monolog\Handler;

use App\Services\Monolog\Handler\Discord\DiscordRecord;
use Monolog\Formatter\FormatterInterface;
use Monolog\Handler\AbstractProcessingHandler;
use Monolog\Handler\HandlerInterface;
use Monolog\Handler\MissingExtensionException;
use Monolog\Logger;
use Monolog\Utils;

class DiscordHandler extends AbstractProcessingHandler
{
    private string        $webhook_url;
    private DiscordRecord $discordRecord;

    /**
     * @throws MissingExtensionException
     */
    public function __construct(
        string  $webhook_url,
        ?string $username = null,
        ?string $avatar_url = null,
        bool    $use_embeds = true,
        bool    $use_inline_embeds = false,
        bool    $show_channel_name = true,
        bool    $include_context_and_extra = true,
                $level = Logger::DEBUG,
        bool    $bubble = true,
        array   $exclude_fields = []
    )
    {
        if (!extension_loaded('curl')) {
            throw new MissingExtensionException('The curl extension is needed to use the SlackWebhookHandler');
        }

        parent::__construct($level, $bubble);

        $this->webhook_url = $webhook_url;

        $this->discordRecord = new DiscordRecord(
            username: $username,
            avatar_url: $avatar_url,
            use_embeds: $use_embeds,
            use_inline_embeds: $use_inline_embeds,
            show_channel_name: $show_channel_name,
            include_context_and_extra: $include_context_and_extra,
            exclude_fields: $exclude_fields
        );
    }

    protected function write(array $record): void
    {
        $postData = $this->discordRecord->getDiscordData($record);
        $postString = Utils::jsonEncode($postData);

        $ch = curl_init();
        $options = [
            CURLOPT_URL            => $this->webhook_url,
            CURLOPT_POST           => true,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER     => ['Content-type: application/json'],
            CURLOPT_POSTFIELDS     => $postString,
        ];

        curl_setopt_array($ch, $options);

        Curl\Util::execute($ch);
    }

    public function setFormatter(FormatterInterface $formatter): HandlerInterface
    {
        parent::setFormatter($formatter);
        $this->discordRecord->setFormatter($formatter);

        return $this;
    }

    public function getFormatter(): FormatterInterface
    {
        $formatter = parent::getFormatter();
        $this->discordRecord->setFormatter($formatter);

        return $formatter;
    }
}
