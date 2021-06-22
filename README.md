# Usage
Split audio files downloaded by OverDrive into multiple files base on chapter information.

- Generate chapter info
- Review chapter info
- Split audio into multiple chapter

Note: The result will be stored in the folder name `../Title Chapters` (Title is book title)

*Get chapters information from folder downloaded by OverDrive*

```
overdrive-tools info <book_dir>
```
After this step, review chater info in file `chapter.info`

*Split audio book into multiple chapters*
```
overdrive-tools split <book_dir>
```