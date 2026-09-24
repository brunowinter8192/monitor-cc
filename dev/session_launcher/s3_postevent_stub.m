#import <AppKit/AppKit.h>
#import <ApplicationServices/ApplicationServices.h>

static NSString *gMode;
static NSString *gLogPath;

static void logLine(NSString *line) {
    NSString *stamp = [[NSDate date] descriptionWithLocale:nil];
    NSString *full = [NSString stringWithFormat:@"%@ %@\n", stamp, line];
    NSFileHandle *fh = [NSFileHandle fileHandleForWritingAtPath:gLogPath];
    if (!fh) {
        [[NSFileManager defaultManager] createFileAtPath:gLogPath contents:nil attributes:nil];
        fh = [NSFileHandle fileHandleForWritingAtPath:gLogPath];
    }
    [fh seekToEndOfFile];
    [fh writeData:[full dataUsingEncoding:NSUTF8StringEncoding]];
    [fh closeFile];
}

static void requestAccess(void) {
    BOOL before = CGPreflightPostEventAccess();
    BOOL onMain = [NSThread isMainThread];
    bool returned = CGRequestPostEventAccess();
    logLine([NSString stringWithFormat:@"request mode=%@ main_thread=%d preflight_before=%d returned=%d preflight_after=%d",
             gMode, onMain, before, returned, CGPreflightPostEventAccess()]);
}

@interface Delegate : NSObject <NSApplicationDelegate>
@end

@implementation Delegate
- (void)applicationDidFinishLaunching:(NSNotification *)note {
    logLine([NSString stringWithFormat:@"started mode=%@ pid=%d", gMode, getpid()]);
    [NSTimer scheduledTimerWithTimeInterval:1.0 repeats:NO block:^(NSTimer *t) {
        if ([gMode isEqualToString:@"bg"]) {
            dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{ requestAccess(); });
        } else {
            requestAccess();
        }
    }];
    [NSTimer scheduledTimerWithTimeInterval:2.0 repeats:YES block:^(NSTimer *t) {
        logLine([NSString stringWithFormat:@"poll preflight=%d", CGPreflightPostEventAccess()]);
    }];
    [NSTimer scheduledTimerWithTimeInterval:50.0 repeats:NO block:^(NSTimer *t) {
        logLine(@"exit");
        [NSApp terminate:nil];
    }];
}
@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        gMode = argc > 1 ? [NSString stringWithUTF8String:argv[1]] : @"main";
        gLogPath = [NSString stringWithFormat:@"/tmp/s3_postevent_%@.log", gMode];
        [[NSFileManager defaultManager] removeItemAtPath:gLogPath error:nil];
        NSApplication *app = [NSApplication sharedApplication];
        [app setActivationPolicy:NSApplicationActivationPolicyAccessory];
        Delegate *d = [[Delegate alloc] init];
        [app setDelegate:d];
        [app run];
    }
    return 0;
}
