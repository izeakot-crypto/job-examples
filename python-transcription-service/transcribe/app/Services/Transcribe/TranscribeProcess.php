<?php


namespace App\Services\Transcribe;


use App\Services\Transcribe\Clients\VoskClient;
use App\Services\Transcribe\Clients\WhisperClient;
use App\Services\Transcribe\Sox\SoxHelper;
use DirectoryIterator;
use Illuminate\Contracts\Filesystem\FileNotFoundException as ContractsFileNotFoundException;
use Illuminate\Contracts\Filesystem\Filesystem;
use Illuminate\Filesystem\FilesystemManager;
use Illuminate\Support\Str;

class TranscribeProcess
{
    private Filesystem $tmpStorage;

    private int $duration_audio   = 0;
    private int $duration_process = 0;

    public function __construct(FilesystemManager              $filesystemManager,
        // private readonly TranscribeClientInterface $transcribeClient,
                                private readonly VoskClient    $voskClient,
                                private readonly WhisperClient $whisperClient)
    {
        $this->tmpStorage = $filesystemManager->disk('converter_audio_tmp');
    }

    public function __destruct()
    {
        $this->clearTmpFolder();
    }

    /**
     * @param string $source_file_name
     * @param string $locale
     * @return array
     * @throws TranscribeServiceException
     */
    public function transcribe(string $source_file_name, string $locale): array
    {
        $this->duration_audio = 0;
        $this->duration_process = 0;

        $tmp_file = Str::random(5) . '_' . basename($source_file_name);
        $tmp_file_wav_1 = $tmp_file . '_1.wav';
        $tmp_file_wav_2 = $tmp_file . '_2.wav';

        try {
            $source_file_name_full = realpath($source_file_name);
            if (empty($source_file_name_full) || !is_file($source_file_name_full)) {
                throw new ContractsFileNotFoundException('Исходный файл не найден.');
            }

            $channels = SoxHelper::getChannelsCount($source_file_name_full);

            $this->splitAudio($source_file_name_full, $tmp_file_wav_1, 1);
            if ($channels > 1) {
                $this->splitAudio($source_file_name_full, $tmp_file_wav_2, 2);
            }

            $start_time = time();
            $data = $this->mergeChannels(
                $this->processFile($tmp_file_wav_1, 1, $locale),
                $channels > 1 ? $this->processFile($tmp_file_wav_2, 2, $locale) : []
            );
            $this->duration_process = time() - $start_time;

            $data = $this->sanitize($data);

            $this->duration_audio = $channels * SoxHelper::getDuration($source_file_name_full);
        }
        catch (ContractsFileNotFoundException $e) {
            throw new TranscribeServiceException($e->getMessage());
        }
        finally {
            $this->tmpStorage->delete($tmp_file_wav_1, $tmp_file_wav_2);
        }

        return $data;
    }

    /**
     * @return int
     */
    public function getLastDurationAudio(): int
    {
        return $this->duration_audio;
    }

    /**
     * @return int
     */
    public function getLastDurationProcess(): int
    {
        return $this->duration_process;
    }


    /**
     * @param string $source_file_name_full
     * @param string $tmp_wav_file_name
     * @param int $channel
     * @throws TranscribeServiceException
     */
    private function splitAudio(string $source_file_name_full, string $tmp_wav_file_name, int $channel): void
    {
        $wav_file_name_full = $this->tmpStorage->path($tmp_wav_file_name);

        SoxHelper::run([
            '--norm=-1', '--temp', '/dev/shm', $source_file_name_full,
            '-t', 'wav', '-r', '8k', $wav_file_name_full,
            'remix', $channel
        ]);

        if (!$this->tmpStorage->exists($tmp_wav_file_name) || ($this->tmpStorage->size($tmp_wav_file_name) < 10)) {
            throw new TranscribeServiceException('Ошибка преобразования формата аудио файла.');
        }
    }

    /**
     * @param string $wav_file_name
     * @param int $channel
     * @param string $locale
     * @return array
     * @throws TranscribeServiceException
     */
    private function processFile(string $wav_file_name, int $channel, string $locale): array
    {
        if (!$f_handle = $this->tmpStorage->readStream($wav_file_name)) {
            throw new TranscribeServiceException('Ошибка открытия временного аудиофайла.');
        }

        try {
//            return $this->transcribeClient->process($f_handle, $channel, $locale);

            // todo временно для тестов работы
            $lang = explode('_', str_replace('-', '_', $locale))[0];
            $client = $lang == 'hi' ? $this->whisperClient : $this->voskClient;
            return $client->process($f_handle, $channel, $locale);

        }
        finally {
            if (is_resource($f_handle)) {
                fclose($f_handle);
            }
        }
    }

    /**
     * @param array $data_1
     * @param array $data_2
     * @return array
     */
    private function mergeChannels(array $data_1, array $data_2): array
    {
        $items = array_merge($data_1, $data_2);
        usort($items, function (array $a, array $b) {
            return $a['start_time'] <=> $b['start_time'];
        });

        return [
            'createdAt' => date('Y-m-d H:i:s'),
            'items'     => $items,
        ];
    }

    /**
     * @param array $data
     * @return array
     */
    private function sanitize(array $data): array
    {
        $is_changed = false;

        foreach ($data['items'] as $key => &$item) {
            // Удалить в начале разговора реплики из одной буквы или гм
            $item['text'] = preg_replace('~^(?:\s*(?:.|гм)(?:\s+|$))+~ui', '', $item['text']);

            // Если удалили всю фразу - удалить item и продолжить проверку
            if (empty($item['text'])) {
                unset($data['items'][$key]);
                $is_changed = true;
                continue;
            }

            // Есть не пустая фраза = начало разговора. После начала разговора не чистим.
            break;
        }

        if ($is_changed) {
            // Обновить ключи результата
            $data['items'] = array_values($data['items']);
        }

        return $data;
    }

    /**
     * Удаляет "потерявшиеся" временные файлы
     */
    private function clearTmpFolder(): void
    {
        $path_tmp = $this->tmpStorage->path('');
        $expired_time = strtotime('-3 hours');
        $iterator = new DirectoryIterator($path_tmp);
        /** @var DirectoryIterator $file */
        foreach ($iterator as $file) {
            if (!$file->isFile()
                || $file->isDot()
                || (
                    ($file->getExtension() != 'wav')
                    &&
                    ($file->getExtension() != 'mp3')
                )
                || ($file->getMTime() > $expired_time)
            ) {
                continue;
            }

            $this->tmpStorage->delete($file->getFilename());
        }
    }

}
