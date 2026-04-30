<?php

namespace App\Console\Commands;

use App\Services\Transcribe\TranscribeProcess;
use Illuminate\Console\Command;

class MyTest extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'test:test';

    /**
     * The console command description.
     *
     * @var string
     */
    protected $description = 'test';

    /**
     * Execute the console command.
     *
     * @param TranscribeProcess $transcribeProcess
     * @return int
     */
    public function handle(TranscribeProcess $transcribeProcess)
    {
        $this->info('ok: ' . $transcribeProcess->getLastDurationAudio());
        return 0;
    }
}
