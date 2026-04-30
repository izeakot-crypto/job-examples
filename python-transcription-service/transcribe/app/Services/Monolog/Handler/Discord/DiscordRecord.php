<?php

namespace App\Services\Monolog\Handler\Discord;

use Monolog\Formatter\FormatterInterface;
use Monolog\Formatter\NormalizerFormatter;
use Monolog\Logger;
use Monolog\Utils;

class DiscordRecord
{
    // https://discord.com/developers/docs/resources/message#embed-object-embed-limits
    private const MAX_LENGTH_CONTENT     = 1990;    // 2000;
    const         MAX_LENGTH_DESCRIPTION = 4086;    // 4096
    const         MAX_LENGTH_FIELD_VALUE = 1014;    // 1024

    private ?string $username   = null;
    private ?string $avatar_url = null;

    /**
     * Whether the message should be added to Discord as embeds (plain text otherwise)
     */
    private bool $use_embeds = true;

    /**
     * Whether the context/extra messages added to Discord as embeds are in a inline style
     */
    private bool $use_inline_embeds = true;

    /**
     * Выводить имя канала в footer
     */
    private bool $show_channel_name = true;

    /**
     * Whether the attachment should include context and extra data
     */
    private bool $include_context_and_extra = false;

    /**
     * Dot separated list of fields to exclude from Discord message. E.g. ['context.field1', 'extra.field2']
     * @var string[]
     */
    private array $exclude_fields = [];

    private ?FormatterInterface $formatter = null;

    private ?NormalizerFormatter $normalizerFormatter = null;

    public function __construct(
        ?string             $username = null,
        ?string             $avatar_url = null,
        bool                $use_embeds = true,
        bool                $use_inline_embeds = true,
        bool                $show_channel_name = true,
        bool                $include_context_and_extra = false,
        array               $exclude_fields = [],
        ?FormatterInterface $formatter = null
    )
    {
        $this
            ->setUsername($username)
            ->setAvatarUrl($avatar_url)
            ->useEmbeds($use_embeds)
            ->useInlineEmbeds($use_inline_embeds)
            ->showChannelName($show_channel_name)
            ->includeContextAndExtra($include_context_and_extra)
            ->excludeFields($exclude_fields)
            ->setFormatter($formatter);

        if ($this->include_context_and_extra) {
            $this->normalizerFormatter = new NormalizerFormatter();
        }
    }

    /**
     * @param array $record
     * @return string[]
     */
    public function getDiscordData(array $record): array
    {
        $data = [
            'username'   => $this->username ?? 'Monolog Bot',
            'avatar_url' => $this->avatar_url,
        ];

        if ($this->formatter !== null && !$this->use_embeds) {
            $message = $this->formatter->format($record);
        }
        else {
            $message = $record['message'];
        }

        $recordData = $this->removeExcludedFields($record);

        if ($this->use_embeds) {
            $embed = [
                'color'       => $this->getAttachmentColor($record['level']),
                'title'       => $record['level_name'],
                'description' => mb_strimwidth($message, 0, self::MAX_LENGTH_DESCRIPTION, ' …'),
                'fields'      => [],
            ];

            if ($this->include_context_and_extra) {
                foreach (['extra', 'context'] as $key) {
                    if (!isset($recordData[$key]) || count($recordData[$key]) === 0) {
                        continue;
                    }

                    if ($this->use_inline_embeds) {
                        $embed['fields'][] = $this->generateAttachmentField(
                            $key,
                            $recordData[$key],
                            false
                        );
                    }
                    else {
                        // Add all extra fields as individual fields in attachment
                        $embed['fields'] = array_merge(
                            $embed['fields'],
                            $this->generateAttachmentFields($recordData[$key], false)
                        );
                    }
                }
            }

            if (($count = count($embed['fields'])) > 25) {
                $embed['fields'] = array_slice($embed['fields'], 0, 24);
                $embed['fields'][] = [
                    'name' => '... and ' . ($count - 24) . ' more fields',
                ];
            }

            if ($this->show_channel_name && $record['channel']) {
                $embed['footer']['text'] = '#' . $record['channel'];
            }

            $data['embeds'] = [$embed];
        }
        else {
            $data['content'] = mb_strimwidth($message, 0, self::MAX_LENGTH_CONTENT, ' …');
        }

        return $data;
    }

    /**
     * Stringifies an array of key/value pairs to be used in attachment fields
     *
     * @param array $fields
     * @return string
     */
    private function stringify(array $fields): string
    {
        /** @var array<array|bool|float|int|string|null> $normalized */
        $normalized = $this->normalizerFormatter->format($fields);

        $hasSecondDimension = count(array_filter($normalized, 'is_array')) > 0;
        $hasOnlyNonNumericKeys = count(array_filter(array_keys($normalized), 'is_numeric')) === 0;

        return $hasSecondDimension || $hasOnlyNonNumericKeys
            ? Utils::jsonEncode($normalized, JSON_PRETTY_PRINT | Utils::DEFAULT_JSON_FLAGS)
            : Utils::jsonEncode($normalized, Utils::DEFAULT_JSON_FLAGS);
    }

    /**
     * @param array $value
     * @return array{title: string, value: string, short: false}
     */
    private function generateAttachmentField(string $title, mixed $value, bool $inline): array
    {
        $value = is_array($value)
            ? sprintf('```%s```', mb_strimwidth($this->stringify($value), 0, self::MAX_LENGTH_FIELD_VALUE, ' …'))
            : $value;

        return [
            'name'   => ucfirst($title),
            'value'  => $value,
            'inline' => $inline,
        ];
    }

    /**
     * @param array $data
     * @param bool $inline
     * @return array<array{title: string, value: string, short: false}>
     */
    private function generateAttachmentFields(array $data, bool $inline): array
    {
        /** @var array<array|string> $normalized */
        $normalized = $this->normalizerFormatter->format($data);

        $fields = [];
        foreach ($normalized as $key => $value) {
            $fields[] = $this->generateAttachmentField((string)$key, $value, $inline);
        }

        return $fields;
    }

    /**
     * @param array $record
     * @return array
     */
    private function removeExcludedFields(array $record): array
    {
        foreach ($this->exclude_fields as $field) {
            $keys = explode('.', $field);
            $node = &$record;
            $lastKey = end($keys);
            foreach ($keys as $key) {
                if (!isset($node[$key])) {
                    break;
                }
                if ($lastKey === $key) {
                    unset($node[$key]);
                    break;
                }
                $node = &$node[$key];
            }
        }

        return $record;
    }

    /**
     * @param int $level
     * @return string
     */
    private function getAttachmentColor(int $level): string
    {
        return match ($level) {
            Logger::DEBUG     => 0x7289DA,   // Discord Blurple
            Logger::INFO      => 0x3498DB,   // Blue
            Logger::NOTICE    => 0x2ECC71,   // Green
            Logger::WARNING   => 0xF1C40F,   // Yellow
            Logger::ERROR     => 0xE74C3C,   // Red
            Logger::CRITICAL  => 0x992D22,   // Dark Red
            Logger::ALERT     => 0x71368A,   // Purple
            Logger::EMERGENCY => 0x1B1B1B,   // Black
        };
    }

    /**
     * @param  ?string $username
     * @return $this
     */
    public function setUsername(?string $username = null): self
    {
        if (!is_null($username) && (mb_strlen($username) == 0)) {
            $username = null;
        }

        $this->username = $username;

        return $this;
    }

    public function setAvatarUrl(?string $avatar_url): DiscordRecord
    {
        if (!is_null($avatar_url) && (mb_strlen($avatar_url) == 0)) {
            $avatar_url = null;
        }
        $this->avatar_url = $avatar_url;
        return $this;
    }

    /**
     * @return $this
     */
    public function useEmbeds(bool $use_embeds = true): self
    {
        $this->use_embeds = $use_embeds;
        return $this;
    }

    /**
     * @return $this
     */
    public function useInlineEmbeds(bool $use_inline_embeds = true): self
    {
        $this->use_inline_embeds = $use_inline_embeds;
        return $this;
    }

    /**
     * @return $this
     */
    public function showChannelName(bool $show_channel_name = true): self
    {
        $this->show_channel_name = $show_channel_name;
        return $this;
    }

    /**
     * @return $this
     */
    public function includeContextAndExtra(bool $include_context_and_extra = true): self
    {
        $this->include_context_and_extra = $include_context_and_extra;

        if ($this->include_context_and_extra) {
            $this->normalizerFormatter = new NormalizerFormatter();
        }

        return $this;
    }

    /**
     * @param string[] $exclude_fields
     * @return $this
     */
    public function excludeFields(array $exclude_fields = []): self
    {
        $this->exclude_fields = $exclude_fields;
        return $this;
    }

    /**
     * @return $this
     */
    public function setFormatter(?FormatterInterface $formatter = null): self
    {
        $this->formatter = $formatter;
        return $this;
    }

}
