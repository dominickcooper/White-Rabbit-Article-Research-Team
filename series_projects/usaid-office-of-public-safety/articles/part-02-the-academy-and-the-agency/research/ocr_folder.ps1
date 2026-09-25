param(
  [Parameter(Mandatory=$true)][string]$InputDirectory,
  [Parameter(Mandatory=$true)][string]$OutputFile
)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
function Await($operation, $resultType) {
  $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } |
    Select-Object -First 1
  $task = $method.MakeGenericMethod($resultType).Invoke($null, @($operation))
  $task.Wait()
  return $task.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
$writer = [System.IO.StreamWriter]::new($OutputFile, $false, [System.Text.UTF8Encoding]::new($false))
try {
  Get-ChildItem -LiteralPath $InputDirectory -Filter '*.png' | Sort-Object Name | ForEach-Object {
    $storage = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($_.FullName)) ([Windows.Storage.StorageFile])
    $stream = Await ($storage.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $writer.WriteLine(('{0}' + [char]9 + '{1}' -f $_.Name, ($result.Text -replace "`r?`n", ' ')))
    $writer.Flush()
    $stream.Dispose()
  }
} finally {
  $writer.Dispose()
}
